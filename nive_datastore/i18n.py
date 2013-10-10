"""
use as import:
from nive_datastore.i18n import _
"""
from translationstring import TranslationStringFactory
_ = TranslationStringFactory('nive_datastore')


from pyramid.i18n import get_localizer
from pyramid.threadlocal import get_current_request

from nive.i18n import translator
from nive.i18n import translate
