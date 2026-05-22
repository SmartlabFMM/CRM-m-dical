# -*- coding: utf-8 -*-
import os
import pickle
from datetime import datetime

import numpy as np

from odoo import api, fields, models
from odoo.exceptions import ValidationError


# ═══════════════════════════════════════════════════════════
#  MODÈLE — Consultation médicale
#  ─────────────────────────────────────────────────────────
#  Workflow conforme au diagramme de cas d'usage :
#   • Médecin   : termine consultation (RDV et facture mis à jour en sudo)
#   • Secrétaire: gère factures depuis menu Factures
#   • Admin     : configure le système
# ═══════════════════════════════════════════════════════════
class MedicalConsultation(models.Model):
    _name = 'medical.consultation'
    _description = 'Consultation médicale'
    _inherit = ['mail.thread']
    _order = 'date desc'

    rendez_vous_id = fields.Many2one(
        'medical.rendezvous',
        string='Rendez-vous',
        required=True,
        ondelete='cascade'
    )
    patient_id = fields.Many2one(
        'medical.patient',
        string='Patient',
        related='rendez_vous_id.patient_id',
        store=True
    )
    medecin_id = fields.Many2one(
        'medical.doctor',
        string='Médecin',
        related='rendez_vous_id.medecin_id',
        store=True
    )
    date = fields.Datetime(
        string='Date consultation',
        default=fields.Datetime.now
    )
    symptomes  = fields.Text(string='Symptômes')
    diagnostic = fields.Text(string='Diagnostic')

    medicament_ids = fields.Many2many(
        'medical.medication',
        'consultation_medication_rel',
        'consultation_id',
        'medication_id',
        string='Médicaments prescrits'
    )
    posologie        = fields.Text(string='Posologie')
    duree_traitement = fields.Integer(
        string='Durée traitement (jours)',
        default=7
    )

    tarif_consultation = fields.Float(
        string='Tarif consultation (TND)',
        default=0.0,
    )

    etat = fields.Selection([
        ('en_cours', 'En cours'),
        ('termine',  'Terminé'),
    ], string='État', default='en_cours', tracking=True)

    facture_id = fields.Many2one(
        'medical.facture',
        string='Facture',
        readonly=True
    )

    pieces_jointes = fields.Many2many('ir.attachment', string='Documents / Images')

    @api.onchange('rendez_vous_id')
    def _onchange_rendez_vous(self):
        if self.rendez_vous_id and self.rendez_vous_id.medecin_id:
            medecin = self.rendez_vous_id.medecin_id
            if medecin.tarif_consultation:
                self.tarif_consultation = medecin.tarif_consultation

    # ═══════════════════════════════════════════════════════
    # MÉDECIN — Action "Terminer"
    # ═══════════════════════════════════════════════════════
    # 1. La consultation passe à 'Terminé' (CRUD autorisé pour médecin)
    # 2. Le RDV lié passe à 'termine' via sudo() (médecin a lecture seule sur RDV)
    # 3. Une facture en brouillon est créée via sudo() (médecin n'a pas CRUD facture)
    # 4. Notification verte de confirmation
    # → La secrétaire validera la facture depuis le menu Factures
    # ═══════════════════════════════════════════════════════
    def terminer(self):
        self.ensure_one()

        # 1. Marquer la consultation comme terminée (CRUD autorisé)
        self.etat = 'termine'

        # 2. Mettre à jour le RDV lié via sudo()
        #    Le médecin a lecture seule sur medical.rendezvous, donc sudo() bypasse
        if self.rendez_vous_id:
            self.rendez_vous_id.sudo().write({'etat': 'termine'})

        # 3. Créer la facture en brouillon via sudo()
        self._creer_facture_brouillon()

        # 4. Audit trail dans le chatter
        self.message_post(
            body=(
                f"<p><b>Consultation terminée par {self.medecin_id.name}.</b></p>"
                f"<p>Une facture a été générée en brouillon. "
                f"La secrétaire la validera depuis le menu Factures.</p>"
            ),
            subject="Consultation terminée"
        )

        # 5. Notification verte non bloquante
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Consultation terminée',
                'message': 'La facture a été générée et sera traitée par la secrétaire.',
                'type': 'success',
                'sticky': False,
            }
        }

    def retour_en_cours(self):
        if self.etat == 'termine':
            self.etat = 'en_cours'
            # Remet aussi le RDV en confirmé (via sudo si médecin connecté)
            if self.rendez_vous_id:
                self.rendez_vous_id.sudo().write({'etat': 'confirme'})

    def _creer_facture_brouillon(self):
        """Crée silencieusement la facture en brouillon.
        Utilise sudo() car le médecin n'a pas les droits CRUD sur medical.facture.
        Méthode privée (préfixe _) donc non exposée aux utilisateurs.
        """
        self.ensure_one()
        if self.facture_id:
            return self.facture_id

        facture = self.env['medical.facture'].sudo().create({
            'consultation_id': self.id,
            'patient_id':      self.patient_id.id,
            'assurance_id':    self.patient_id.assurance_id.id
                               if self.patient_id.assurance_id else False,
            'date_facture':    fields.Date.today(),
            'montant_total':   self.tarif_consultation,
        })
        self.sudo().facture_id = facture
        return facture