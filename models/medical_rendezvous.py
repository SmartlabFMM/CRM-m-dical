# -*- coding: utf-8 -*-


from odoo import api, fields, models
from odoo.exceptions import ValidationError




MOTS_CLES_GRAVES = [
    # Cardiovasculaire
    'douleur thoracique', 'oppression', 'palpitation',
    # Respiratoire
    'dyspnée', 'essoufflement', 'difficulté respir', 'étouffement',
    # Neurologique
    'perte de conscience', 'syncope', 'convulsion', 'paralysie',
    'confusion', 'vertige sévère',
    # Hémorragique
    'hémorragie', 'saignement abondant', 'vomissement de sang',
    # Général
    'fièvre élevée', 'fièvre >39', 'douleur intense', 'douleur aiguë',
    'choc', 'traumatisme',
]

# Négations pour éviter les faux positifs ("pas de douleur thoracique")
NEGATIONS = [
    'pas de ', "pas d'", 'sans ', 'aucun ', 'aucune ',
    'absence de ', "absence d'", 'ni ',
]

SEUIL_PRIORITAIRE = 4   # score ≥ 4  → Prioritaire
SEUIL_URGENT      = 6   # score ≥ 6  → Urgent


def _contient_symptome_grave(texte):
    """
    Détecte un symptôme grave en gérant les négations.
    Ex : 'pas de douleur thoracique' → False (correctement)
         'douleur thoracique intense' → True
    """
    if not texte:
        return False
    texte = str(texte).lower()
    for mc in MOTS_CLES_GRAVES:
        position = texte.find(mc)
        if position >= 0:
            # Vérifier qu'il n'y a pas de négation dans les 20 caractères avant
            contexte_avant = texte[max(0, position - 20):position]
            if not any(neg in contexte_avant for neg in NEGATIONS):
                return True
    return False


# ═══════════════════════════════════════════════════════════════════════════
#  MODÈLE
# ═══════════════════════════════════════════════════════════════════════════

class MedicalRendezvous(models.Model):
    _name        = 'medical.rendezvous'
    _description = 'Rendez-vous médical'
    _inherit     = ['mail.thread', 'mail.activity.mixin']
    _order       = 'date_debut desc'

    # ─────────────────────────────────────────────────────────────────────
    # CHAMPS
    # ─────────────────────────────────────────────────────────────────────

    reference = fields.Char(
        string='Référence',
        readonly=True,
        copy=False,
        default='Nouveau',
    )

    patient_id = fields.Many2one(
        'medical.patient',
        string='Patient',
        required=True,
        tracking=True,
        ondelete='restrict',
    )

    medecin_id = fields.Many2one(
        'medical.doctor',
        string='Médecin',
        required=True,
        tracking=True,
        ondelete='restrict',
    )

    salle_id = fields.Many2one(
        'medical.room',
        string='Salle',
        required=True,
        tracking=True,
        ondelete='restrict',
        domain=[('state', '!=', 'maintenance')],
        help="Seules les salles disponibles ou occupées sont proposées.",
    )

    date_debut = fields.Datetime(
        string='Date début',
        required=True,
        tracking=True,
    )

    date_fin = fields.Datetime(
        string='Date fin',
        required=True,
    )

    motif = fields.Text(
        string='Motif de consultation',
        required=True,
    )

    etat = fields.Selection(
        selection=[
            ('confirme', 'Confirmé'),
            ('termine',  'Terminé'),
            ('annule',   'Annulé'),
        ],
        string='État',
        default='confirme',
        required=True,
        tracking=True,
    )

    consultation_ids = fields.One2many(
        'medical.consultation',
        'rendez_vous_id',
        string='Consultations',
    )

    # ── Champs de scoring (RENOMMÉS) ──────────────────────────────────────

    priorite_score = fields.Selection(
        selection=[
            ('urgent',      '🔴 Urgent'),
            ('prioritaire', '🟡 Prioritaire'),
            ('normal',      '🟢 Normal'),
        ],
        string='Priorité',
        compute='_compute_priorite_score',
        store=True,
        tracking=True,
        help="Calculée automatiquement par le scoring métier SmartLab.\n"
             "Critères : âge, maladie chronique, symptômes, antécédents.",
    )

    score_priorite = fields.Integer(
        string='Score de priorité',
        compute='_compute_priorite_score',
        store=True,
        help="Score brut (0–11). Prioritaire ≥ 4, Urgent ≥ 6.",
    )

    details_priorite = fields.Char(
        string='Détails du score',
        compute='_compute_priorite_score',
        store=True,
        help="Décomposition critère par critère — transparence totale.",
    )

    # ─────────────────────────────────────────────────────────────────────
    # SCORING MÉTIER — calcul automatique
    # ─────────────────────────────────────────────────────────────────────

    @api.depends(
        'patient_id',
        'patient_id.age',
        'patient_id.chronic_diseases',
        'motif',
        'consultation_ids',
    )
    def _compute_priorite_score(self):
        """Déclenché à la création et à chaque modification des dépendances."""
        for rec in self:
            score, classe, details = self._scoring_rules(rec)
            rec.score_priorite   = score
            rec.priorite_score   = classe
            rec.details_priorite = details

    @staticmethod
    def _scoring_rules(rec):
        """
        Applique les règles de scoring SmartLab.
        Retourne (score: int, classe: str, details: str).

        Critères :
          +3  Âge > 65 ans          (fragilité — référence HAS)
          +1  Âge 40-65 ans         (risque modéré)
          +3  Maladie chronique      (comorbidité — surveillance renforcée)
          +4  Symptôme grave détecté (avec gestion des négations)
          +1  Antécédents médicaux   (> 3 consultations passées)
        """
        score   = 0
        details = []

        # ── Critère 1 : Âge ─────────────────────────────────────────────
        age = 0
        if rec.patient_id and rec.patient_id.age:
            try:
                age = int(rec.patient_id.age)
            except (TypeError, ValueError):
                age = 0

        if age > 65:
            score += 3
            details.append('Âge > 65 (+3)')
        elif age >= 40:
            score += 1
            details.append('Âge 40-65 (+1)')

        # ── Critère 2 : Maladie chronique ────────────────────────────────
        if rec.patient_id and rec.patient_id.chronic_diseases:
            mc = str(rec.patient_id.chronic_diseases).strip().lower()
            if mc and mc not in ('aucune', 'none', 'nan', '0', 'false', ''):
                score += 3
                details.append('Maladie chronique (+3)')

        # ── Critère 3 : Symptômes graves (BUG 2 CORRIGÉ : négations) ─────
        texte_motif = ''
        for attr in ('motif', 'symptomes'):
            val = getattr(rec, attr, None)
            if val:
                texte_motif += ' ' + str(val).lower()

        if _contient_symptome_grave(texte_motif):
            score += 4
            details.append('Symptôme grave (+4)')

        # ── Critère 4 : Antécédents (BUG 1 CORRIGÉ : sans rec.id) ────────
        if rec.patient_id:
            nb_consult = rec.env['medical.consultation'].search_count([
                ('patient_id', '=', rec.patient_id.id),
            ])
            if nb_consult > 3:
                score += 1
                details.append('Antécédents (+1)')

        # ── Classification finale ────────────────────────────────────────
        if score >= SEUIL_URGENT:
            classe = 'urgent'
        elif score >= SEUIL_PRIORITAIRE:
            classe = 'prioritaire'
        else:
            classe = 'normal'

        detail_str = '; '.join(details) if details else 'Aucun critère déclencheur'
        return score, classe, detail_str

    # ─────────────────────────────────────────────────────────────────────
    # Action manuelle : forcer le recalcul (bouton "Actualiser")
    # ─────────────────────────────────────────────────────────────────────

    def action_recalculer_priorite(self):
        """Bouton 'Recalculer priorité' dans la vue formulaire."""
        self._compute_priorite_score()
        return {
            'type': 'ir.actions.client',
            'tag':  'display_notification',
            'params': {
                'title':   'Priorité recalculée',
                'message': f'Score : {self.score_priorite} → {self.priorite_score}',
                'type':    'success',
                'sticky':  False,
            },
        }

    # ─────────────────────────────────────────────────────────────────────
    # WORKFLOW — créer une consultation
    # ─────────────────────────────────────────────────────────────────────

    def action_creer_consultation(self):
        self.ensure_one()
        if self.consultation_ids:
            return {
                'type':      'ir.actions.act_window',
                'name':      'Consultation',
                'res_model': 'medical.consultation',
                'res_id':    self.consultation_ids[0].id,
                'view_mode': 'form',
                'target':    'current',
            }
        return {
            'type':      'ir.actions.act_window',
            'name':      'Nouvelle Consultation',
            'res_model': 'medical.consultation',
            'view_mode': 'form',
            'target':    'current',
            'context':   {'default_rendez_vous_id': self.id},
        }

    # ─────────────────────────────────────────────────────────────────────
    # CRUD
    # ─────────────────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Référence automatique
            if vals.get('reference', 'Nouveau') == 'Nouveau':
                vals['reference'] = (
                    self.env['ir.sequence'].next_by_code('medical.appointment')
                    or 'Nouveau'
                )
        records = super().create(vals_list)
        # Occupation des salles
        records._post_marquer_salles_occupees()
        return records

    def write(self, vals):
        salles_avant = self.mapped('salle_id')
        result       = super().write(vals)
        salles_apres = self.mapped('salle_id')
        (salles_avant | salles_apres)._recalculer_occupation()
        return result

    def _post_marquer_salles_occupees(self):
        for rdv in self:
            if rdv.salle_id and rdv.etat == 'confirme':
                rdv.salle_id._recalculer_occupation_pour_creneau(
                    date_debut=rdv.date_debut,
                    date_fin=rdv.date_fin,
                )

    # ─────────────────────────────────────────────────────────────────────
    # ONCHANGE — alertes temps réel dans le formulaire
    # ─────────────────────────────────────────────────────────────────────

    @api.onchange('medecin_id', 'date_debut', 'date_fin')
    def _onchange_avertir_medecin(self):
        if not (self.medecin_id and self.date_debut and self.date_fin):
            return
        conflit = self.env['medical.rendezvous'].search([
            ('medecin_id', '=',  self.medecin_id.id),
            ('etat',       '!=', 'annule'),
            ('id',         '!=', self._origin.id or 0),
            ('date_debut', '<',  self.date_fin),
            ('date_fin',   '>',  self.date_debut),
        ], limit=1)
        if conflit:
            self.medecin_id = False
            raise ValidationError(
                f"⛔  MÉDECIN INDISPONIBLE\n\n"
                f"Le Dr {conflit.medecin_id.name} a déjà un rendez-vous "
                f"sur ce créneau :\n"
                f"  [{conflit.reference}]  {conflit.patient_id.name}\n"
                f"  {conflit.date_debut.strftime('%d/%m/%Y %H:%M')}"
                f" → {conflit.date_fin.strftime('%H:%M')}\n\n"
                f"Veuillez choisir un autre médecin ou modifier le créneau."
            )

    @api.onchange('salle_id', 'date_debut', 'date_fin')
    def _onchange_avertir_salle(self):
        if not (self.salle_id and self.date_debut and self.date_fin):
            return
        if self.salle_id.state == 'maintenance':
            self.salle_id = False
            raise ValidationError(
                "🔧  SALLE EN MAINTENANCE\n\n"
                "Cette salle est actuellement en maintenance et ne peut "
                "pas être réservée.\nVeuillez en choisir une autre."
            )
        conflit = self.env['medical.rendezvous'].search([
            ('salle_id',   '=',  self.salle_id.id),
            ('etat',       '!=', 'annule'),
            ('id',         '!=', self._origin.id or 0),
            ('date_debut', '<',  self.date_fin),
            ('date_fin',   '>',  self.date_debut),
        ], limit=1)
        if conflit:
            self.salle_id = False
            raise ValidationError(
                f"🚫  SALLE DÉJÀ OCCUPÉE\n\n"
                f"La salle est déjà réservée sur ce créneau :\n"
                f"  [{conflit.reference}]  Dr {conflit.medecin_id.name}"
                f"  /  {conflit.patient_id.name}\n"
                f"  {conflit.date_debut.strftime('%d/%m/%Y %H:%M')}"
                f" → {conflit.date_fin.strftime('%H:%M')}\n\n"
                f"Veuillez choisir une autre salle ou modifier le créneau."
            )

    # ─────────────────────────────────────────────────────────────────────
    # CONTRAINTES
    # ─────────────────────────────────────────────────────────────────────

    @api.constrains('date_debut', 'date_fin')
    def _verifier_dates(self):
        for rec in self:
            if rec.date_fin and rec.date_debut and rec.date_fin <= rec.date_debut:
                raise ValidationError(
                    "⛔  La date de fin doit être strictement après la date de début !"
                )

    @api.constrains('medecin_id', 'date_debut', 'date_fin', 'etat')
    def _verifier_disponibilite_medecin(self):
        for rec in self:
            if rec.etat == 'annule':
                continue
            conflits = self.search([
                ('medecin_id', '=',  rec.medecin_id.id),
                ('etat',       '!=', 'annule'),
                ('id',         '!=', rec.id),
                ('date_debut', '<',  rec.date_fin),
                ('date_fin',   '>',  rec.date_debut),
            ])
            if conflits:
                lignes = '\n'.join(
                    f"  • [{c.reference}]  {c.patient_id.name}"
                    f"  —  {c.date_debut.strftime('%d/%m/%Y %H:%M')}"
                    f" → {c.date_fin.strftime('%H:%M')}"
                    for c in conflits
                )
                raise ValidationError(
                    f"🚫  CONFLIT MÉDECIN\n\n"
                    f"Le Dr {rec.medecin_id.name} a déjà un rendez-vous "
                    f"sur ce créneau :\n\n{lignes}\n\n"
                    f"Choisissez un autre créneau ou un autre médecin."
                )

    @api.constrains('salle_id', 'date_debut', 'date_fin', 'etat')
    def _verifier_disponibilite_salle(self):
        for rec in self:
            if not rec.salle_id or rec.etat == 'annule':
                continue
            if rec.salle_id.state == 'maintenance':
                raise ValidationError(
                    f"🔧  La salle « {rec.salle_id.name} » est en maintenance "
                    f"et ne peut pas être réservée."
                )
            conflits = self.search([
                ('salle_id',   '=',  rec.salle_id.id),
                ('etat',       '!=', 'annule'),
                ('id',         '!=', rec.id),
                ('date_debut', '<',  rec.date_fin),
                ('date_fin',   '>',  rec.date_debut),
            ])
            if conflits:
                lignes = '\n'.join(
                    f"  • [{c.reference}]  Dr {c.medecin_id.name}"
                    f"  /  {c.patient_id.name}"
                    f"  —  {c.date_debut.strftime('%d/%m/%Y %H:%M')}"
                    f" → {c.date_fin.strftime('%H:%M')}"
                    for c in conflits
                )
                raise ValidationError(
                    f"🚫  CONFLIT SALLE\n\n"
                    f"La salle « {rec.salle_id.name} » est déjà occupée "
                    f"sur ce créneau :\n\n{lignes}\n\n"
                    f"Choisissez une autre salle ou un autre créneau."
                )

    # ─────────────────────────────────────────────────────────────────────
    # TRANSITIONS D'ÉTAT
    # ─────────────────────────────────────────────────────────────────────

    def terminer(self):
        self.ensure_one()
        self.write({'etat': 'termine'})

    def annuler(self):
        self.ensure_one()
        self.write({'etat': 'annule'})

    def confirmer(self):
        self.ensure_one()
        self.write({'etat': 'confirme'})