# -*- coding: utf-8 -*-
from odoo import models, fields


class MedicalSpecialty(models.Model):
    _name = 'medical.specialty'
    _description = 'Spécialité Médicale'
    _order = 'name'

    name = fields.Char(string='Spécialité', required=True)
    code = fields.Char(string='Code', size=10)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Actif', default=True)

    doctor_ids = fields.One2many('medical.doctor', 'specialty_id', string='Médecins')
    doctor_count = fields.Integer(string='Nombre de médecins', compute='_compute_doctor_count')

    def _compute_doctor_count(self):
        for rec in self:
            rec.doctor_count = len(rec.doctor_ids)
