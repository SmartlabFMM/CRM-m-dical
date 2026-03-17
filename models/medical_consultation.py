# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MedicalConsultation(models.Model):
    _name = 'medical.consultation'
    _description = 'Consultation médicale'
    _inherit = ['mail.thread']
    _order = 'date desc'

    #  Attributs 
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

    #  Ordonnance
    medicament_ids = fields.Many2many(
        'medical.medication',
        'consultation_medication_rel',
        'consultation_id',
        'medication_id',
        string='Médicaments prescrits'
    )
    posologie         = fields.Text(string='Posologie')
    duree_traitement  = fields.Integer(string='Durée traitement (jours)', default=7)

    etat = fields.Selection([
        ('en_cours', 'En cours'),
        ('termine',  'Terminé'),
    ], string='État', default='en_cours', tracking=True)

    #  Relations 
    facture_id = fields.Many2one(
        'medical.facture',
        string='Facture',
        readonly=True
    )

    #  Méthodes 
    def terminer(self):
        self.etat = 'termine'
        self.rendez_vous_id.etat = 'termine'

    def creer_facture(self):
        self.ensure_one()
        if self.facture_id:
            return
        facture = self.env['medical.facture'].create({
            'consultation_id': self.id,
            'patient_id':      self.patient_id.id,
            'assurance_id':    self.patient_id.assurance_id.id,
            'date_facture':    fields.Date.today(),
        })
        self.facture_id = facture
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facture',
            'res_model': 'medical.facture',
            'res_id': facture.id,
            'view_mode': 'form',
        }

    def imprimer(self):
        return self.env.ref(
            'smartlab_medical.action_report_consultation'
        ).report_action(self)
