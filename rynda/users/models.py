# -*- coding: utf-8 -*-

import os
import random
import base64
import hashlib
import string

from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _

from post_office import mail


class UserAuthCode(object):
    def __init__(self, secret, salt_len=8, hash=hashlib.sha256):
        self.secret = secret
        self.salt_len = salt_len
        self.hash = hash

    def salt(self):
        s = [random.choice(string.letters + string.digits)
             for i in xrange(self.salt_len)]
        return "".join(s)

    def digest(self, user, salt):
        # Use username, email and date_joined to generate digest
        auth_message = ''.join((self.secret, user.username, user.email,
                               str(user.date_joined), salt))
        md = self.hash()
        md.update(auth_message)

        return base64.urlsafe_b64encode(md.digest()).rstrip('=')

    def auth_code(self, user):
        salt = self.salt()
        digest = self.digest(user, salt)

        return "%s%s" % (salt, digest)

    def is_valid(self, user, auth_code):
        salt = auth_code[:self.salt_len]
        digest = auth_code[self.salt_len:]

        # CAVEAT: Make sure UserAuthCode cannot be used to reactivate locked
        # profiles.
        if user.last_login >= user.date_joined:
            return False

        return digest == self.digest(user, salt)


class Profile(models.Model):
    """
    User profile
    """
    class Meta:
        ordering = ['user']
        verbose_name = _("Profile")
        verbose_name_plural = _("Profiles")

    MALE, FEMALE, UNKNOWN = (1, 2, 0)
    SEX_CHOICES = (
        (UNKNOWN, _("Unknown")),
        (MALE, _("Male")),
        (FEMALE, _("Female")),
    )

    user = models.OneToOneField(User)
    is_public = models.BooleanField(_("Public"), default=False)
    phones = models.CharField(max_length=255, blank=True)
    about_me = models.TextField(default='', blank=True)
    birthday = models.DateField(blank=True, null=True)
    gender = models.IntegerField(_("Gender"), choices=SEX_CHOICES, default=UNKNOWN)

    def __unicode__(self):
        return "Profile for %s" % self.user.username


def create_new_user(first_name, last_name, password, email):
    user = User(
        first_name=first_name,
        last_name=last_name,
        email=email,
        username=email,
        is_staff=False,
        is_active=False
    )
    user.set_password(password),
    user.save()
    Profile.objects.create(user=user)
    notify_new_user(user)
    return user


def _file_get_contents(fname):
    abs_path = os.path.dirname(__file__)
    file_path = os.path.join(abs_path, fname)
    with open(file_path, 'r') as f:
        return f.read()


def notify_new_user(user):
    """ Уведомляем нового пользователя о регистрации """
    # file_path = "templates/emails/registration_confirm/%s"
    # subj = _file_get_contents(file_path % "short.txt")
    # text = _file_get_contents(file_path % "email.txt")
    # html = _file_get_contents(file_path % "email.html")
    activation_code = UserAuthCode(settings.SECRET_KEY).auth_code(user)

    mail.send(
        [user],
        # subject=subj, message=text, html_message=html,
        template="registration confirmation",
        context={
            'user': user,
            'activation_code': activation_code,
        }
    )


def activate_user(user, code):
    encoder = UserAuthCode(settings.SECRET_KEY)
    if encoder.is_valid(user, code):
        user.is_active = True
        user.save()
        return True
    return False
