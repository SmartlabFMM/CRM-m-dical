# -*- coding: utf-8 -*-


import os
import pickle
from datetime import datetime

import numpy as np

from odoo import api, fields, models
from odoo.exceptions import ValidationError




class MedicalRendezvous(models.Model):
   


    _name        = 'medical.rendezvous'
    _description = 'Rendez-vous médical'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date_debut desc'

    # ─────────────────────────────────────────────────────────────────────────
    # CHAMPS
    # ─────────────────────────────────────────────────────────────────────────

    reference = fields.Char(
        string='Référence',
        readonly=True,
        copy=False,
        default='Nouveau',
    )

    patient_id = fields.Many2one(
        'medical.patient',
        string='Patient',
        required=True,
        tracking=True,
        ondelete='restrict',
    )

    medecin_id = fields.Many2one(
        'medical.doctor',
        string='Médecin',
        required=True,
        tracking=True,
        ondelete='restrict',
    )

    salle_id = fields.Many2one(
        'medical.room',
        string='Salle',
        required=True,                      
        tracking=True,
        ondelete='restrict',
        domain=[('state', '!=', 'maintenance')],  # filtre salles en maintenance
        help="Seules les salles disponibles ou occupées sont proposées.",
    )

    date_debut = fields.Datetime(
        string='Date début',
        required=True,
        tracking=True,
    )

    date_fin = fields.Datetime(
        string='Date fin',
        required=True,
    )

    motif = fields.Text(
        string='Motif de consultation',
        required=True,
    )

    etat = fields.Selection(
        selection=[
            ('confirme', 'Confirmé'),
            ('termine',  'Terminé'),
            ('annule',   'Annulé'),
        ],
        string='État',
        default='confirme',
        required=True,
        tracking=True,
    )

    consultation_ids = fields.One2many(
        'medical.consultation',
        'rendez_vous_id',
        string='Consultations',
    )

    priorite_ml = fields.Selection(
        selection=[
            ('urgent',      '🔴Urgent'),
            ('prioritaire', '🟡 Prioritaire'),
            ('normal',      '🟢 Normal'),
        ],
        string='Priorité ML',
        readonly=True,
        tracking=True,
        help="Calculée automatiquement par le modèle Random Forest.",
    )

    # ─────────────────────────────────────────────────────────────────────────
    # MODÈLE ML
    # ─────────────────────────────────────────────────────────────────────────

    def _charger_modele(self):
        """Charge et retourne (modele, encoder) depuis les .pkl du dossier ml/."""
        dossier = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ml')
        with open(os.path.join(dossier, 'smartlab_triage_model.pkl'),  'rb') as f:
            modele  = pickle.load(f)
        with open(os.path.join(dossier, 'smartlab_label_encoder.pkl'), 'rb') as f:
            encoder = pickle.load(f)
        return modele, encoder

    def _predire_priorite(self, patient_id, date_debut):
        """
        Prédit 'urgent' | 'prioritaire' | 'normal' via Random Forest.
        Features : [age, sexe_enc, jour_semaine, mois, est_age]
        Repli sur règles métier si le modèle est indisponible.
        """
        age = 0
        try:
            modele, encoder = self._charger_modele()
            if patient_id:
                patient  = self.env['medical.patient'].browse(patient_id)
                age      = int(patient.age or 0)
                sexe_enc = 0 if getattr(patient, 'gender', 'male') == 'male' else 1
            else:
                sexe_enc = 0
            X        = np.array([[
                age, sexe_enc,
                date_debut.weekday() if date_debut else 0,
                date_debut.month     if date_debut else 1,
                1 if age > 60 else 0,
            ]])
            pred_enc = modele.predict(X)[0]
            return encoder.inverse_transform([pred_enc])[0]
        except Exception as exc:
            
            return 'urgent' if age > 60 else ('prioritaire' if age >= 40 else 'normal')



    @api.model_create_multi
    def create(self, vals_list):
 
        for vals in vals_list:
            # 1. Référence
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code('medical.appointment')
                    or 'Nouveau'
                )
            # 2. Priorité ML
            if vals.get('patient_id') and vals.get('date_debut'):
                date = vals['date_debut']
                if isinstance(date, str):
                    date = datetime.strptime(date[:19], '%Y-%m-%d %H:%M:%S')
                vals['priorite_ml'] = self._predire_priorite(
                    patient_id=vals['patient_id'],
                    date_debut=date,
                )

        records = super().create(vals_list)    

        # 3. POST-CONDITION —marquer les salles occupées
        records._post_marquer_salles_occupees()
        return records

    def write(self, vals):
  
        salles_avant = self.mapped('salle_id')          # salles AVANT

        result = super().write(vals)                    # ← contraintes 

        salles_apres = self.mapped('salle_id')          # salles APRÈS
        (salles_avant | salles_apres)._recalculer_occupation()
        return result

  
    def _post_marquer_salles_occupees(self):
  
        for rdv in self:
            if rdv.salle_id and rdv.etat == 'confirme':
                rdv.salle_id._recalculer_occupation_pour_creneau(
                    date_debut=rdv.date_debut,
                    date_fin=rdv.date_fin,
                )
            

    # ─────────────────────────────────────────────────────────────────────────
    # ONCHANGE — alertes temps réel dans le formulaire (non bloquantes)
    # ─────────────────────────────────────────────────────────────────────────

    @api.onchange('patient_id', 'date_debut')
    def _onchange_priorite(self):
        """Recalcule la priorité ML dès que le patient ou la date change."""
        if self.patient_id and self.date_debut:
            self.priorite_ml = self._predire_priorite(
                patient_id=self.patient_id.id,
                date_debut=self.date_debut,
            )

    @api.onchange('medecin_id', 'date_debut', 'date_fin')
    def _onchange_avertir_medecin(self):
        """
        BLOQUANT — lève une ValidationError si le médecin est déjà occupé
        sur ce créneau. Le champ est réinitialisé et l'utilisateur doit
        corriger avant de continuer.
        """
        if not (self.medecin_id and self.date_debut and self.date_fin):
            return

        conflit = self.env['medical.rendezvous'].search([
            ('medecin_id', '=',  self.medecin_id.id),
            ('etat',       '!=', 'annule'),
            ('id',         '!=', self._origin.id or 0),
            ('date_debut', '<',  self.date_fin),
            ('date_fin',   '>',  self.date_debut),
        ], limit=1)

        if conflit:
            # Réinitialise le champ médecin pour forcer une nouvelle saisie
            self.medecin_id = False
            raise ValidationError(
                f"  MÉDECIN INDISPONIBLE\n\n"
                f"Le Dr {conflit.medecin_id.name} a déjà un rendez-vous "
                f"sur ce créneau :\n"
                f"  [{conflit.reference}]  {conflit.patient_id.name}\n"
                f"  {conflit.date_debut.strftime('%d/%m/%Y %H:%M')}"
                f" → {conflit.date_fin.strftime('%H:%M')}\n\n"
                f"Veuillez choisir un autre médecin ou modifier le créneau."
            )

    @api.onchange('salle_id', 'date_debut', 'date_fin')
    def _onchange_avertir_salle(self):
        """
        BLOQUANT — lève une ValidationError si la salle est déjà réservée
        ou en maintenance. La salle est réinitialisée et l'utilisateur doit
        en choisir une autre avant de continuer.
        """
        if not (self.salle_id and self.date_debut and self.date_fin):
            return

        # Cas 1 : salle en maintenance
        if self.salle_id.state == 'maintenance':
            self.salle_id = False
            raise ValidationError(
                "🔧  SALLE EN MAINTENANCE\n\n"
                "Cette salle est actuellement en maintenance et ne peut "
                "pas être réservée.\n"
                "Veuillez en choisir une autre."
            )

        # Cas 2 : chevauchement avec un RDV existant
        conflit = self.env['medical.rendezvous'].search([
            ('salle_id',   '=',  self.salle_id.id),
            ('etat',       '!=', 'annule'),
            ('id',         '!=', self._origin.id or 0),
            ('date_debut', '<',  self.date_fin),
            ('date_fin',   '>',  self.date_debut),
        ], limit=1)

        if conflit:
            # Réinitialise le champ salle pour forcer une nouvelle saisie
            self.salle_id = False
            raise ValidationError(
                f" SALLE DÉJÀ OCCUPÉE\n\n"
                f"La salle est déjà réservée sur ce créneau :\n"
                f"  [{conflit.reference}]  Dr {conflit.medecin_id.name}"
                f"  /  {conflit.patient_id.name}\n"
                f"  {conflit.date_debut.strftime('%d/%m/%Y %H:%M')}"
                f" → {conflit.date_fin.strftime('%H:%M')}\n\n"
                f"Veuillez choisir une autre salle ou modifier le créneau."
            )

    # ─────────────────────────────────────────────────────────────────────────
    # CONTRAINTE ① — Cohérence des dates
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('date_debut', 'date_fin')
    def _verifier_dates(self):
        """date_fin doit être strictement postérieure à date_debut."""
        for rec in self:
            if rec.date_fin and rec.date_debut and rec.date_fin <= rec.date_debut:
                raise ValidationError(
                    "⛔  La date de fin doit être strictement après la date de début !"
                )

    # ─────────────────────────────────────────────────────────────────────────
    # CONTRAINTE ② — Disponibilité du MÉDECIN
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('medecin_id', 'date_debut', 'date_fin', 'etat')
    def _verifier_disponibilite_medecin(self):
        """
        Bloque la sauvegarde si le médecin a déjà un RDV sur ce créneau.

       """
        for rec in self:
            if rec.etat == 'annule':
                continue                # un RDV annulé ne bloque plus personne

            conflits = self.search([
                ('medecin_id', '=',  rec.medecin_id.id),
                ('etat',       '!=', 'annule'),
                ('id',         '!=', rec.id),
                ('date_debut', '<',  rec.date_fin),
                ('date_fin',   '>',  rec.date_debut),
            ])

            if conflits:
                lignes = '\n'.join(
                    f"  • [{c.reference}]  {c.patient_id.name}"
                    f"  —  {c.date_debut.strftime('%d/%m/%Y %H:%M')}"
                    f" → {c.date_fin.strftime('%H:%M')}"
                    for c in conflits
                )
                raise ValidationError(
                    f"🚫  CONFLIT MÉDECIN\n\n"
                    f"Le Dr {rec.medecin_id.name} a déjà un rendez-vous "
                    f"sur ce créneau :\n\n"
                    f"{lignes}\n\n"
                    f"Choisissez un autre créneau ou un autre médecin."
                )

    # ─────────────────────────────────────────────────────────────────────────
    # CONTRAINTE ③ — Disponibilité de la SALLE
    # ─────────────────────────────────────────────────────────────────────────

    @api.constrains('salle_id', 'date_debut', 'date_fin', 'etat')
    def _verifier_disponibilite_salle(self):
        """
        Bloque la sauvegarde si la salle est déjà réservée sur ce créneau
        ou si elle est en maintenance.
        """
        for rec in self:
            if not rec.salle_id or rec.etat == 'annule':
                continue

            # Salle en maintenance → toujours bloquée
            if rec.salle_id.state == 'maintenance':
                raise ValidationError(
                    f"🔧  La salle « {rec.salle_id.name} » est en maintenance "
                    f"et ne peut pas être réservée."
                )

            # Chevauchement avec un autre RDV sur la même salle
            conflits = self.search([
                ('salle_id',   '=',  rec.salle_id.id),
                ('etat',       '!=', 'annule'),
                ('id',         '!=', rec.id),
                ('date_debut', '<',  rec.date_fin),
                ('date_fin',   '>',  rec.date_debut),
            ])

            if conflits:
                lignes = '\n'.join(
                    f"  • [{c.reference}]  Dr {c.medecin_id.name}"
                    f"  /  {c.patient_id.name}"
                    f"  —  {c.date_debut.strftime('%d/%m/%Y %H:%M')}"
                    f" → {c.date_fin.strftime('%H:%M')}"
                    for c in conflits
                )
                raise ValidationError(
                    f"🚫  CONFLIT SALLE\n\n"
                    f"La salle « {rec.salle_id.name} » est déjà occupée "
                    f"sur ce créneau :\n\n"
                    f"{lignes}\n\n"
                    f"Choisissez une autre salle ou un autre créneau."
                )

    # ─────────────────────────────────────────────────────────────────────────
    # TRANSITIONS D'ÉTAT
    # ─────────────────────────────────────────────────────────────────────────

    def terminer(self):
        """
        Termine le RDV.
        write() recalculera automatiquement l'état de la salle.
        """
        self.ensure_one()
        self.write({'etat': 'termine'})

    def annuler(self):
     
        self.ensure_one()
        self.write({'etat': 'annule', 'priorite_ml': 'urgent'})

    def confirmer(self):
        
        self.ensure_one()
        self.write({'etat': 'confirme'})