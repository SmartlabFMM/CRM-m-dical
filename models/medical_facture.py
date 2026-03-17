# -*- coding: utf-8 -*-
from odoo import models, fields, api


class Medicalfacture(models.Model):
    _name = 'medical.facture'
    _description = 'Facture médicale'
    _inherit = ['mail.thread']
    _order = 'date_facture desc'

    #  Attributs 
    reference = fields.Char(
        string='Référence',
        readonly=True,
        default='Nouveau'
    )
    consultation_id = fields.Many2one(
        'medical.consultation',
        string='Consultation',
        required=True
    )
    patient_id = fields.Many2one(
        'medical.patient',
        string='Patient',
        required=True
    )
    assurance_id = fields.Many2one(
        'medical.assurance',
        string='Assurance'
    )
    date_facture     = fields.Date(
        string='Date facture',
        default=fields.Date.today
    )
    montant_total    = fields.Float(
        string='Montant total (TND)',
        required=True,
        default=0.0
    )
    montant_assurance = fields.Float(
        string='Part assurance (TND)',
        compute='_calculer_montants',
        store=True
    )
    montant_patient  = fields.Float(
        string='Part patient (TND)',
        compute='_calculer_montants',
        store=True
    )
    etat = fields.Selection([
        ('brouillon', 'Brouillon'),
        ('valide',    'Validée'),
        ('payee',     'Payée'),
        ('annulee',   'Annulée'),
    ], string='État', default='brouillon', tracking=True)

    #  Méthodes 
    @api.model
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'medical.facture'
                ) or 'Nouveau'
        return super().create(vals_list)

    @api.depends('montant_total', 'assurance_id', 'assurance_id.taux_couverture')
    def _calculer_montants(self):
        for rec in self:
            if rec.assurance_id and rec.montant_total:
                taux = rec.assurance_id.taux_couverture / 100
                rec.montant_assurance = rec.montant_total * taux
                rec.montant_patient   = rec.montant_total - rec.montant_assurance
            else:
                rec.montant_assurance = 0.0
                rec.montant_patient   = rec.montant_total

    def valider(self):
        self.etat = 'valide'

    def payer(self):
        self.etat = 'payee'

    def calculer_montants(self):
        self._calculer_montants()

    def imprimer(self):
        return self.env.ref(
            'smartlab_medical.action_report_facture'
        ).report_action(self)