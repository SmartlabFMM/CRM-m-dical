# -*- coding: utf-8 -*-
from odoo import models, fields, api


class Medicalfacture(models.Model):
    _name = 'medical.facture'
    _description = 'Facture médicale'
    _inherit = ['mail.thread']
    _order = 'date_facture desc'

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
    date_facture = fields.Date(
        string='Date facture',
        default=fields.Date.today
    )

   
    # Avant : c'était aussi computed mais sans source → restait à 0
    # Maintenant : la valeur vient de creer_facture() via tarif_consultation
    # Et reste modifiable manuellement si besoin
    montant_total = fields.Float(
        string='Montant total (TND)',
        default=0.0,
        tracking=True,  # Trace les changements dans le chatter
    )

    # Ces deux champs sont calculés automatiquement depuis montant_total + assurance
    montant_assurance = fields.Float(
        string='Part assurance (TND)',
        compute='_calculer_montants',
        store=True      # Stocké en base pour les recherches et rapports
    )
    montant_patient = fields.Float(
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

    @api.model
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'medical.facture'
                ) or 'Nouveau'
        return super().create(vals_list)

    
    # @api.depends liste les champs qui déclenchent le recalcul automatique
    # Avant : fonctionnait mais montant_total était toujours 0 donc inutile
    @api.depends('montant_total', 'assurance_id', 'assurance_id.taux_couverture')
    def _calculer_montants(self):
        for rec in self:
            if rec.assurance_id and rec.montant_total:
                # Calcul de la part prise en charge par l'assurance
                taux = rec.assurance_id.taux_couverture / 100
                rec.montant_assurance = rec.montant_total * taux
                # Ce que le patient doit payer = total - part assurance
                rec.montant_patient   = rec.montant_total - rec.montant_assurance
            else:
                # Pas d'assurance → le patient paie tout
                rec.montant_assurance = 0.0
                rec.montant_patient   = rec.montant_total

    
    # Avant : appelait _calculer_montants() mais montant_total était à 0
    # Maintenant : utile si l'utilisateur modifie montant_total manuellement
    def calculer_montants(self):
        self._calculer_montants()

    def valider(self):
        self.etat = 'valide'

    def payer(self):
        self.etat = 'payee'