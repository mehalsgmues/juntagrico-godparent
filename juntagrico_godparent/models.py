from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from juntagrico.config import Config
from juntagrico.entity.member import Member
from juntagrico.util.temporal import weekday_choices, weekdays
from multiselectfield import MultiSelectField
from django.utils.translation import gettext as _
from multiselectfield.db.fields import MSFList

from juntagrico_godparent.querysets import GodchildQuerySet, GodparentQuerySet
from juntagrico_godparent.util.utils import is_godparent, is_godchild


LANGUAGES = (('de', 'Deutsch'),
             ('fr', 'Français'),
             ('it', 'Italiano'),
             ('ro', 'Rumantsch dal Grischun'),
             ('en', 'English'),
             ('pt', 'Português'),
             ('es', 'Español'),
             ('ot', _('Andere (Bitte unten angeben)')))


def week_slots_choices():
    return [
        (
            weekday, (
                (str(num) + 'am', _('Vormittag')),
                (str(num) + 'pm', _('Nachmittag')),
                (str(num) + 'ev', _('Abend')),
            )
        ) for num, weekday in weekday_choices
    ]


class Criteria(models.Model):
    member = models.OneToOneField(Member, verbose_name=Config.vocabulary('member'), on_delete=models.CASCADE)
    creation_date = models.DateField(_('Erstellungsdatum'), auto_now_add=True)
    languages = MultiSelectField(_('Verständigung'), choices=LANGUAGES,
                                 help_text=_('Wähle die Sprachen aus, die du sprichst.'))
    slots = MultiSelectField(_('Verfügbarkeit'), choices=week_slots_choices(),
                             help_text=_('Während diesen Zeitfenstern bin ich üblicherweise verfügbar und könnte mich '
                                         'zu einer Einführung bzw. einem ersten gemeinsamen Einsatz treffen.'))
    children = models.BooleanField(_(f'Ich habe Kinder, die ich zu den Einsätzen '
                                     f'bei {Config.organisation_name()} mitbringe'),
                                   help_text=_('Für Neumitglieder mit Kindern hat sich eine Einführung '
                                               'durch ein Gotte/Götti mit Kindern bewährt.'))
    comments = models.TextField(_('Bemerkungen und weitere Kriterien'), max_length=1000, default='', blank=True,
                                help_text=_('Was möchtest du uns noch mitteilen? Was sollten wir sonst noch beachten, bei der Vermittlung?'))

    @property
    def depot(self):
        if self.member.subscription_future:
            return self.member.subscription_future.future_depot or self.member.subscription_future.depot
        elif self.member.subscription_current:
            return self.member.subscription_current.future_depot or self.member.subscription_current.depot
        return None

    def clean(self):
        if hasattr(self, 'member') and is_godparent(self.member) and is_godchild(self.member):
            raise ValidationError(_('Mitglied kann nicht Gotte/Götti und Neumtiglied gleichzeitig sein'))

    def admin_change_url_name(self):
        return "admin:juntagrico_godparent_" + self.__class__.__name__.lower() + "_change"

    def __str__(self):
        return str(self.member)

    class Meta:
        abstract = True


class Godparent(Criteria):
    max_godchildren = models.PositiveIntegerField(
        _('Anzahl Neumitglieder'), validators=[MinValueValidator(1)], default=1,
        help_text=_('Wie viele Neumitglieder könntest du betreuen?')
    )

    objects = GodparentQuerySet.as_manager()

    def remaining_godchildren(self):
        return self.max_godchildren - self.godchild_set.count()

    class Meta:
        verbose_name = _('Gotte/Götti')
        verbose_name_plural = _('Gotte/Göttis')
        permissions = (('can_make_matches', _('Kann Gotte/Götti vermitteln')),)


class Godchild(Criteria):
    talents = models.TextField(_('Interessen & Begabungen'), max_length=1000, default='', blank=True,
                               help_text=_('Hast du bestimmte Talente oder Fähigkeiten?'))
    godparent = models.ForeignKey(Godparent, verbose_name=_('Gotte/Götti'), on_delete=models.SET_NULL,
                                  null=True, blank=True)

    objects = GodchildQuerySet.as_manager()

    def matching_languages(self):
        if self.godparent:
            return MSFList(self.languages.choices, set(self.languages).intersection(set(self.godparent.languages)))
        return set()

    def matching_slots(self):
        if self.godparent:
            # attach weekday to choice names
            choices = {k: weekdays[int(k[0])] + " " + v for k, v in self.slots.choices.items()}
            return MSFList(choices, set(self.slots).intersection(set(self.godparent.slots)))
        return set()

    def matching_areas(self):
        if self.godparent:
            return set(self.member.areas.all()).intersection(set(self.godparent.member.areas.all()))
        return set()

    class Meta:
        verbose_name = _('Neumitglied')
        verbose_name_plural = _('Neumitglieder')
