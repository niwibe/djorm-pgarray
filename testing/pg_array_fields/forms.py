# -*- coding: utf-8 -*-
from django.forms.models import ModelForm
from .models import IntModel


class IntArrayFrom(ModelForm):
    class Meta:
        model = IntModel