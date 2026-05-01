# -*- coding: utf-8 -*-
from odoo import models, fields, api


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

   
    # Pré-rempli automatiquement depuis le tarif du médecin (voir _onchange_medecin)
    # Mais reste modifiable manuellement par l'utilisateur
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

    
    # @api.onchange réagit à la modification du champ 'medecin_id' dans le formulaire
    # Cela ne fonctionne que si medecin_id n'est pas 'related' (ici il l'est)
    # Donc on utilise aussi _compute au niveau du create()
    @api.onchange('medecin_id')
    def _onchange_medecin(self):
        # Si un médecin est sélectionné et que son tarif est défini
        if self.medecin_id and self.medecin_id.tarif_consultation:
            # On copie son tarif dans le champ tarif_consultation
            # L'utilisateur peut toujours le modifier après
            self.tarif_consultation = self.medecin_id.tarif_consultation

    
    # Avant : terminer() ne créait pas de facture, elle restait à 0
    def terminer(self):
        self.etat = 'termine'
        self.rendez_vous_id.etat = 'termine'
        # Appel automatique à creer_facture() à la fin de la consultation
        self.creer_facture()

    def creer_facture(self):
        self.ensure_one()
        # Si une facture existe déjà, on ne crée pas de doublon
        if self.facture_id:
            return
        facture = self.env['medical.facture'].create({
            'consultation_id': self.id,
            'patient_id':      self.patient_id.id,
            # ✅ CORRIGÉ — On vérifie que assurance_id existe avant de le passer
            # Avant : plantait si le patient n'avait pas d'assurance
            'assurance_id':    self.patient_id.assurance_id.id
                               if self.patient_id.assurance_id else False,
            'date_facture':    fields.Date.today(),
            # ✅ CORRIGÉ — On passe maintenant le tarif saisi dans la consultation
            # Avant : montant_total n'était jamais passé → restait à 0
            'montant_total':   self.tarif_consultation,
        })
        # On lie la facture à la consultation
        self.facture_id = facture
        # On redirige l'utilisateur vers la facture créée
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facture',
            'res_model': 'medical.facture',
            'res_id': facture.id,
            'view_mode': 'form',
        }