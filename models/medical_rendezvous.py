# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class Medicalrendezvous(models.Model):
    _name = 'medical.rendezvous'
    _description = 'Rendez-vous'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_debut desc'

    #  Attributs 
    reference = fields.Char(
        string='Référence',
        readonly=True,
        default='Nouveau'
    )
    patient_id = fields.Many2one(
        'medical.patient',
        string='Patient',
        required=True,
        tracking=True
    )
    medecin_id = fields.Many2one(
        'medical.doctor',
        string='Médecin',
        required=True,
        tracking=True
    )
    salle_id = fields.Many2one(
        'medical.room',
        string='Salle',
        tracking=True
    )
    date_debut = fields.Datetime(
        string='Date début',
        required=True,
        tracking=True
    )
    date_fin = fields.Datetime(
        string='Date fin',
        required=True
    )
    etat = fields.Selection([
        ('brouillon', 'Nouveau'),
        ('confirme',  'Confirmé'),
        ('en_cours',  'En cours'),
        ('termine',   'Terminé'),
        ('annule',    'Annulé'),
    ], string='État', default='brouillon', tracking=True)

    motif = fields.Text(string='Motif de consultation')

    #  Relations 
    consultation_ids = fields.One2many(
        'medical.consultation', 'rendez_vous_id',
        string='Consultations'
    )

    #  Méthodes 
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'medical.appointment'
                ) or 'Nouveau'
        return super().create(vals_list)
    def confirmer(self):
        self.etat = 'confirme'

    def annuler(self):
        self.etat = 'annule'

    def envoyer_rappel(self):
        self.ensure_one()
        template = self.env.ref(
            'smartlab_medical.email_template_rdv_rappel',
            raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)

    @api.constrains('date_debut', 'date_fin')
    def _verifier_dates(self):
        for rec in self:
            if rec.date_fin and rec.date_debut:
                if rec.date_fin <= rec.date_debut:
                    raise ValidationError(
                        "La date de fin doit être après la date de début !"
                    )


class MedicalRoom(models.Model):
    _name = 'medical.room'
    _description = 'Salle de consultation'

    #  Attributs 
    nom      = fields.Char(string='Nom', required=True)
    code     = fields.Char(string='Code', required=True)
    capacite = fields.Integer(string='Capacité', default=1)
    etage    = fields.Integer(string='Étage', default=0)
    etat     = fields.Selection([
        ('disponible',  'Disponible'),
        ('occupee',     'Occupée'),
        ('maintenance', 'En maintenance'),
    ], string='État', default='disponible')

    #  Méthodes 
    def reserver(self):
        self.etat = 'occupee'

    def est_disponible(self):
        self.ensure_one()
        return self.etat == 'disponible'

