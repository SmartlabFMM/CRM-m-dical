# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MedicalDoctor(models.Model):
    _name = 'medical.doctor'
    _description = 'Médecin'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # ─ Identification 
    reference = fields.Char(
        string='Référence', copy=False, readonly=True, default='Nouveau'
    )
    name = fields.Char(string='Nom complet', required=True, tracking=True)
    cin = fields.Char(string='CIN', size=8)
    gender = fields.Selection([
        ('male', 'Masculin'),
        ('female', 'Féminin'),
    ], string='Sexe')

    #  Professionnel 
    specialty_id = fields.Many2one(
        'medical.specialty', string='Spécialité', required=True, tracking=True
    )
    license_number = fields.Char(string='Numéro d\'ordre')
    years_experience = fields.Integer(string='Années d\'expérience')

    #─ Contact 
    phone = fields.Char(string='Téléphone')
    email = fields.Char(string='Email')

    #  Planning 
    room_id = fields.Many2one('medical.room', string='Salle assignée')
    consultation_duration = fields.Integer(
        string='Durée consultation (min)', default=30
    )
    working_hours = fields.Char(string='Horaires de travail', default='08:00-17:00')

    active = fields.Boolean(string='Actif', default=True)
    state = fields.Selection([
        ('active', 'Actif'),
        ('on_leave', 'En congé'),
        ('inactive', 'Inactif'),
    ], string='Statut', default='active', tracking=True)

    #  Séquence automatique 
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code('medical.doctor') or 'Nouveau'
        return super().create(vals_list)

    #  Actions état 
    def action_set_active(self):      
        self.state = 'active'

    def action_set_on_leave(self):     
        self.state = 'on_leave'

def action_set_inactive(self):      
    self.state = 'inactive'

