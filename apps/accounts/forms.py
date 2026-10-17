"""
Formulaires allauth branchés sur notre mixin Tailwind (01_BACKEND.md §4, 06_FRONTEND_GUIDE.md).

Pourquoi : les gabarits allauth 65 rendent les champs via l'élément `fields` (qui appelle
`form.as_p`). En donnant des classes Tailwind aux widgets à la source (ici), les pages de
connexion/inscription/mot de passe héritent de la charte sans réécrire chaque gabarit.
Ces classes sont référencées par le réglage `ACCOUNT_FORMS` (voir config/settings/base.py).
Le mixin pose les classes du thème sombre « console » (SETUP.md §6), cohérent avec le reste
de l'application.
"""

from allauth.account.forms import (
    ChangePasswordForm,
    LoginForm,
    ResetPasswordForm,
    ResetPasswordKeyForm,
    SetPasswordForm,
    SignupForm,
)

from apps.core.forms import TailwindFormMixin


class TailwindLoginForm(TailwindFormMixin, LoginForm):
    pass


class TailwindSignupForm(TailwindFormMixin, SignupForm):
    pass


class TailwindResetPasswordForm(TailwindFormMixin, ResetPasswordForm):
    pass


class TailwindResetPasswordKeyForm(TailwindFormMixin, ResetPasswordKeyForm):
    pass


class TailwindChangePasswordForm(TailwindFormMixin, ChangePasswordForm):
    pass


class TailwindSetPasswordForm(TailwindFormMixin, SetPasswordForm):
    pass
