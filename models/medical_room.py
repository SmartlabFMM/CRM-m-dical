# -*- coding: utf-8 -*-
"""
=============================================================================
MODULE     : SmartLab — medical.room
FILE       : models/medical_room.py
DESCRIPTION: Salles de consultation avec gestion automatique de l'occupation.

LOGIQUE D'OCCUPATION (UC 6a — post-condition) :
─────────────────────────────────────────────────────────────────────────────
  L'état de la salle est mis à jour automatiquement par medical.rendezvous
  via la méthode _recalculer_occupation().

  Règles :
    • 'maintenance' → jamais modifié automatiquement (priorité absolue)
    • Au moins 1 RDV confirmé/actif sur ce créneau → 'occupied'
    • Aucun RDV actif → 'available'

  Les actions manuelles (action_set_*) restent disponibles pour les
  responsables de salle (ex : mise en maintenance).
=============================================================================
"""

from odoo import api, fields, models
from datetime import datetime


class MedicalRoom(models.Model):
    _name        = 'medical.room'
    _description = 'Salle de Consultation'
    _order       = 'name'

    # ─────────────────────────────────────────────────────────────────────────
    # CHAMPS DE BASE
    # ─────────────────────────────────────────────────────────────────────────

    name = fields.Char(
        string='Nom de la salle',
        required=True,
    )

    floor = fields.Integer(
        string='Étage',
        default=0,
    )

    capacity = fields.Integer(
        string='Capacité',
        default=1,
        help="Nombre maximum de patients pouvant être pris en charge simultanément.",
    )

    active = fields.Boolean(
        string='Actif',
        default=True,
    )

    state = fields.Selection(
        selection=[
            ('available',   'Disponible'),
            ('occupied',    'Occupée'),
            ('maintenance', 'En maintenance'),
        ],
        string='État',
        default='available',
        required=True,
        tracking=True,          # historique des changements d'état dans le chatter
    )

    notes = fields.Text(string='Notes')

    # ─────────────────────────────────────────────────────────────────────────
    # RELATION INVERSE — rendez-vous liés à cette salle
    # ─────────────────────────────────────────────────────────────────────────

    rendezvous_ids = fields.One2many(
        comodel_name='medical.rendezvous',
        inverse_name='salle_id',
        string='Rendez-vous',
        help="Tous les rendez-vous planifiés dans cette salle.",
    )

    # Compteur affiché dans la vue liste/kanban
    rendezvous_count = fields.Integer(
        string='Nb RDV',
        compute='_compute_rendezvous_count',
    )

    # ─────────────────────────────────────────────────────────────────────────
    # CHAMPS CALCULÉS
    # ─────────────────────────────────────────────────────────────────────────

    @api.depends('rendezvous_ids', 'rendezvous_ids.etat')
    def _compute_rendezvous_count(self):
        """Nombre total de rendez-vous non annulés pour cette salle."""
        for room in self:
            room.rendezvous_count = self.env['medical.rendezvous'].search_count([
                ('salle_id', '=', room.id),
                ('etat',     '!=', 'annule'),
            ])

    # ─────────────────────────────────────────────────────────────────────────
    # MÉTHODE PRINCIPALE — recalcul automatique de l'occupation  (UC 6a)
    # ─────────────────────────────────────────────────────────────────────────

    def _recalculer_occupation(self):
        """
        POST-CONDITION UC 6a : « Salle marquée occupée pour le créneau. »

        Met à jour l'état de chaque salle (self) selon les RDV existants
        À L'INSTANT T (datetime.now()) :

            ┌─────────────────────────────────────────────────────────┐
            │ État 'maintenance' → JAMAIS modifié automatiquement      │
            │ RDV confirmé en cours à l'instant T → 'occupied'         │
            │ Aucun RDV en cours → 'available'                         │
            └─────────────────────────────────────────────────────────┘

        Appelée par medical.rendezvous après create() et write().

        Note : Pour un agenda futur (non temps-réel), remplacez
               datetime.now() par le champ date_debut du RDV concerné.
        """
        maintenant = fields.Datetime.now()

        for room in self:
            # La maintenance est gérée manuellement, on ne touche pas
            if room.state == 'maintenance':
                continue

            # Y a-t-il un RDV confirmé qui chevauche l'instant présent ?
            rdv_en_cours = self.env['medical.rendezvous'].search_count([
                ('salle_id',   '=',  room.id),
                ('etat',       '=',  'confirme'),
                ('date_debut', '<=', maintenant),
                ('date_fin',   '>',  maintenant),
            ])

            nouvel_etat = 'occupied' if rdv_en_cours else 'available'

            if room.state != nouvel_etat:
                # sudo() : évite les problèmes de droits lors de l'écriture
                # depuis un contexte utilisateur limité
                room.sudo().write({'state': nouvel_etat})

    def _recalculer_occupation_pour_creneau(self, date_debut, date_fin):
        """
        Variante de _recalculer_occupation pour marquer la salle occupée
        sur un créneau FUTUR (utile lors de la création d'un RDV planifié).

        Paramètres :
            date_debut (datetime) : début du créneau
            date_fin   (datetime) : fin du créneau

        Règle : si au moins 1 RDV confirmé chevauche ce créneau → 'occupied'
        """
        for room in self:
            if room.state == 'maintenance':
                continue

            rdv_sur_creneau = self.env['medical.rendezvous'].search_count([
                ('salle_id',   '=',  room.id),
                ('etat',       '=',  'confirme'),
                ('date_debut', '<',  date_fin),
                ('date_fin',   '>',  date_debut),
            ])

            nouvel_etat = 'occupied' if rdv_sur_creneau else 'available'
            if room.state != nouvel_etat:
                room.sudo().write({'state': nouvel_etat})

    # ─────────────────────────────────────────────────────────────────────────
    # ACTIONS MANUELLES (inchangées + améliorées)
    # ─────────────────────────────────────────────────────────────────────────

    def action_set_available(self):
        """Force la salle en 'Disponible' (action manuelle responsable)."""
        self.write({'state': 'available'})

    def action_set_occupied(self):
        """Force la salle en 'Occupée' (action manuelle responsable)."""
        self.write({'state': 'occupied'})

    def action_set_maintenance(self):
        """
        Met la salle en maintenance.
        ⚠️  Vérifie qu'il n'y a pas de RDV confirmés sur les prochaines 24h.
        """
        for room in self:
            rdv_imminent = self.env['medical.rendezvous'].search([
                ('salle_id',   '=',  room.id),
                ('etat',       '=',  'confirme'),
                ('date_fin',   '>',  fields.Datetime.now()),
            ], limit=1)

            if rdv_imminent:
                # Import ici pour éviter la circularité
                from odoo.exceptions import UserError
                raise UserError(
                    f"⚠️ Impossible de mettre la salle « {room.name} » en maintenance.\n"
                    f"Un rendez-vous confirmé est planifié :\n"
                    f"  {rdv_imminent.reference} — {rdv_imminent.patient_id.name}\n"
                    f"  Le {rdv_imminent.date_debut.strftime('%d/%m/%Y à %H:%M')}"
                )

        self.write({'state': 'maintenance'})

    # ─────────────────────────────────────────────────────────────────────────
    # BOUTON SMART — ouvre les RDV de la salle
    # ─────────────────────────────────────────────────────────────────────────

    def action_voir_rendezvous(self):
        """Ouvre la liste des rendez-vous de cette salle (bouton stat)."""
        self.ensure_one()
        return {
            'type':    'ir.actions.act_window',
            'name':    f'Rendez-vous — {self.name}',
            'res_model': 'medical.rendezvous',
            'view_mode': 'list,form',
            'domain':  [('salle_id', '=', self.id)],
            'context': {'default_salle_id': self.id},
        }