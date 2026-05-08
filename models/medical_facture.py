# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError  


class MedicalFacture(models.Model):
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
    # ─── FIX PROBLÈME 8 ─────────────────────────────────────
    # store=True : le champ est sauvegardé en base de données
    # Sans ça, l'assurance disparaît à l'affichage
    assurance_id = fields.Many2one(
        'medical.assurance',
        string='Assurance',
        store=True
    )
    date_facture = fields.Date(
        string='Date facture',
        default=fields.Date.today
    )
 
    montant_total = fields.Float(
        string='Montant total (TND)',
        default=0.0,
        tracking=True,
    )
 
    montant_assurance = fields.Float(
        string='Part assurance (TND)',
        compute='_calculer_montants',
        store=True
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
 
    # ─── FIX PROBLÈME 6 & 7 ─────────────────────────────────
    # AVANT : quand on choisissait une consultation, patient et montant
    #         restaient vides → erreur "Missing required fields"
    # APRÈS : onchange sur consultation_id remplit tout automatiquement
    @api.onchange('consultation_id')
    def _onchange_consultation(self):
        if self.consultation_id:
            self.patient_id    = self.consultation_id.patient_id
            self.montant_total = self.consultation_id.tarif_consultation
            if self.consultation_id.patient_id.assurance_id:
                self.assurance_id = self.consultation_id.patient_id.assurance_id
 
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
 
    @api.model
    def create(self, vals_list):
        for vals in vals_list:
            # Génération automatique de la référence (FAC/2026/0001)
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'medical.facture'
                ) or 'Nouveau'
 
            # ─── FIX PROBLÈME 6 & 7 (création depuis terminer()) ────
            # Quand la facture est créée programmatiquement depuis terminer(),
            # on s'assure que patient et montant sont bien remplis
            if vals.get('consultation_id') and not vals.get('patient_id'):
                consultation = self.env['medical.consultation'].browse(
                    vals['consultation_id']
                )
                vals['patient_id']    = consultation.patient_id.id
                vals['montant_total'] = consultation.tarif_consultation
                if consultation.patient_id.assurance_id:
                    vals['assurance_id'] = consultation.patient_id.assurance_id.id
 
        return super().create(vals_list)
 
    def calculer_montants(self):
        """Bouton 'Recalculer' dans le formulaire."""
        self._calculer_montants()
 
    # ─── FIX PROBLÈME 4 ─────────────────────────────────────
    def valider(self):
        self.etat = 'valide'
 
    def payer(self):
        self.etat = 'payee'
 
    # ─── FIX PROBLÈME 5 ─────────────────────────────────────
    def retour_brouillon(self):
        """Validée → Brouillon si erreur avant paiement."""
        if self.etat == 'valide':
            self.etat = 'brouillon'
 
    def retour_valide(self):
        """Payée → Validée si clic 'Payée' par erreur."""
        if self.etat == 'payee':
            self.etat = 'valide'
    def unlink(self):
        for facture in self:
            if facture.etat == 'valide':
                raise UserError("Facture validée, suppression impossible.")
            if facture.etat == 'payee':
                raise UserError("Facture déjà réglée, suppression impossible.")
        return super(MedicalFacture, self).unlink()