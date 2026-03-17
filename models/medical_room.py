# -*- coding: utf-8 -*-
from odoo import models, fields


class MedicalRoom(models.Model):
    _name = 'medical.room'
    _description = 'Salle de Consultation'
    _order = 'name'

    name = fields.Char(string='Nom de la salle', required=True)
    floor = fields.Integer(string='Étage', default=0)
    capacity = fields.Integer(string='Capacité', default=1)
    active = fields.Boolean(string='Actif', default=True)
    state = fields.Selection([
        ('available', 'Disponible'),
        ('occupied', 'Occupée'),
        ('maintenance', 'En maintenance'),
    ], string='État', default='available', required=True)
    notes = fields.Text(string='Notes')

    #  Actions de changement d'état 
    def action_set_available(self):
        self.state = 'available'

    def action_set_occupied(self):
        self.state = 'occupied'

    def action_set_maintenance(self):
        self.state = 'maintenance'

