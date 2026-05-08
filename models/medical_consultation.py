# -*- coding: utf-8 -*-
import os
import pickle
from datetime import datetime
 
import numpy as np
 
from odoo import api, fields, models
from odoo.exceptions import ValidationError
 
 
# ═══════════════════════════════════════════════════════════
#  MODÈLE 1 — Consultation médicale
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
    # Ces deux champs sont remplis automatiquement depuis le rendez-vous choisi
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
    # ─── FIX PROBLÈME 10 ────────────────────────────────────
    # AVANT : onchange sur 'medecin_id' → ne se déclenche jamais
    #         car medecin_id est un champ 'related' (calculé automatiquement)
    # APRÈS : onchange sur 'rendez_vous_id' → se déclenche quand
    #         la secrétaire choisit un rendez-vous dans le formulaire
    @api.onchange('rendez_vous_id')
    def _onchange_rendez_vous(self):
        if self.rendez_vous_id and self.rendez_vous_id.medecin_id:
            medecin = self.rendez_vous_id.medecin_id
            if medecin.tarif_consultation:
                self.tarif_consultation = medecin.tarif_consultation
 
    def terminer(self):
        self.ensure_one()
        self.etat = 'termine'
        self.rendez_vous_id.etat = 'termine'
        return self.creer_facture()

    def retour_en_cours(self):
        if self.etat == 'termine':
            self.etat = 'en_cours'

    def creer_facture(self):
        self.ensure_one()
        if self.facture_id:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Facture',
                'res_model': 'medical.facture',
                'res_id': self.facture_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
        facture = self.env['medical.facture'].create({
            'consultation_id': self.id,
            'patient_id':      self.patient_id.id,
            'assurance_id':    self.patient_id.assurance_id.id
                               if self.patient_id.assurance_id else False,
            'date_facture':    fields.Date.today(),
            'montant_total':   self.tarif_consultation,
        })
        self.facture_id = facture
        return {
            'type': 'ir.actions.act_window',
            'name': 'Facture',
            'res_model': 'medical.facture',
            'res_id': facture.id,
            'view_mode': 'form',
            'target': 'current',
        }