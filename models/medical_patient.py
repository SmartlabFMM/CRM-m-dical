# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date
import re


class MedicalPatient(models.Model):
    _name = 'medical.patient'
    _description = 'Patient'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'
    _rec_name = 'name'

    # ── Identification ──────────────────────────────────────────────
    reference = fields.Char(
        string='Référence', copy=False, readonly=True, default='Nouveau'
    )
    name = fields.Char(string='Nom complet', required=True, tracking=True)
    cin = fields.Char(string='CIN', size=8, copy=False)
    gender = fields.Selection([
        ('male', 'Masculin'),
        ('female', 'Féminin'),
    ], string='Sexe', required=True)
    birthdate = fields.Date(string='Date de naissance')
    age = fields.Integer(string='Âge', compute='_compute_age', store=True)
    blood_type = fields.Selection([
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ], string='Groupe sanguin')

    # ── Contact ─────────────────────────────────────────────────────
    phone = fields.Char(string='Téléphone')
    email = fields.Char(string='Email')
    address = fields.Text(string='Adresse')

    # ── Médical ─────────────────────────────────────────────────────
    allergies = fields.Text(string='Allergies connues')
    chronic_diseases = fields.Text(string='Maladies chroniques')
    notes = fields.Text(string='Notes médicales')

    active = fields.Boolean(string='Actif', default=True)
    state = fields.Selection([
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
    ], string='Statut', default='active', tracking=True)

    # ─asssurance
    assurance_id = fields.Many2one(
        'medical.assurance',
        string='Assurance',
        tracking=True,
        ondelete='set null',
    )

    # ── Workflow ─────────────────────────────────────────────────────
    def action_nouveau_rendezvous(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Nouveau Rendez-vous',
            'res_model': 'medical.rendezvous',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_patient_id': self.id},
        }

    #  Compute 
    @api.depends('birthdate')
    def _compute_age(self):
        today = date.today()
        for rec in self:
            if rec.birthdate and rec.birthdate <= today:
                rec.age = today.year - rec.birthdate.year - (
                    (today.month, today.day) < (rec.birthdate.month, rec.birthdate.day) 
                )
            else:
                rec.age = 0

    #  Séquence automatique 
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code('medical.patient') or 'Nouveau'
        return super().create(vals_list)

    #  Contrainte CIN unique 
    @api.constrains('cin')
    def _check_cin(self):
        for rec in self:
            if rec.cin:
                if not re.fullmatch(r'\d{8}', rec.cin):
                    raise ValidationError("Le CIN doit contenir exactement 8 chiffres (sans lettres).")
                duplicate = self.search([('cin', '=', rec.cin), ('id', '!=', rec.id)])
                if duplicate:
                    raise ValidationError(f"Un patient avec le CIN {rec.cin} existe déjà.")

    @api.constrains('birthdate')
    def _check_date_naissance(self):
        for rec in self:
            if rec.birthdate and rec.birthdate > date.today():
                raise ValidationError(f"La date de naissance ne peut pas être dans le futur. "
                                      f"Valeur saisie : {rec.birthdate}")