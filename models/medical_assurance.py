# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MedicalAssurance(models.Model):
    _name = 'medical.assurance'
    _description = 'Assurance Médicale'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'nom asc'
 
    # ─── FIX PROBLÈME 9 ─────────────────────────────────────
    # AVANT : pas de _rec_name → Odoo affichait "medical.assurance,12"
    # APRÈS : le champ affiché est 'nom'
    _rec_name = 'nom'
 
    nom = fields.Char(
        string='Nom de la compagnie',
        required=True,
        tracking=True
    )
    code = fields.Char(
        string='Code assurance',
        required=True,
        tracking=True
    )
    taux_couverture = fields.Float(
        string='Taux de couverture (%)',
        digits=(5, 2),
        default=0.0,
        tracking=True
    )
    telephone = fields.Char(string='Téléphone contact')
    email     = fields.Char(string='Email')
    adresse   = fields.Text(string='Adresse')
    actif     = fields.Boolean(
        string='Actif',
        default=True,
        tracking=True
    )
 
    nombre_patients = fields.Integer(
        string='Nombre de patients',
        compute='_calculer_nombre_patients',
        store=False
    )
    nombre_factures = fields.Integer(
        string='Nombre de factures',
        compute='_calculer_nombre_factures',
        store=False
    )
 
    patient_ids = fields.One2many(
        'medical.patient',
        'assurance_id',
        string='Patients couverts'
    )
    facture_ids = fields.One2many(
        'medical.facture',
        'assurance_id',
        string='Factures'
    )
 
    @api.depends('patient_ids')
    def _calculer_nombre_patients(self):
        for rec in self:
            rec.nombre_patients = len(rec.patient_ids)
 
    @api.depends('facture_ids')
    def _calculer_nombre_factures(self):
        for rec in self:
            rec.nombre_factures = len(rec.facture_ids)
 
    def calculer_couverture(self, montant_total):
        """Retourne le montant pris en charge par l'assurance."""
        self.ensure_one()
        return montant_total * (self.taux_couverture / 100)
 
    def voir_patients(self):
        """Ouvre la liste des patients couverts."""
        return {
            'type': 'ir.actions.act_window',
            'name': f'Patients — {self.nom}',
            'res_model': 'medical.patient',
            'view_mode': 'list,form',
            'domain': [('assurance_id', '=', self.id)],
        }
 
    def voir_factures(self):
        # ─── FIX PROBLÈME (original) ─────────────────────────
        # AVANT : 'res_model': 'medical.invoice'  →  ModèleNotFound en prod
        # APRÈS : 'res_model': 'medical.facture'  →  cohérent avec le reste
        return {
            'type': 'ir.actions.act_window',
            'name': f'Factures — {self.nom}',
            'res_model': 'medical.facture',
            'view_mode': 'list,form',
            'domain': [('assurance_id', '=', self.id)],
        }
  