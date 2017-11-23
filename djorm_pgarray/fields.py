# -*- coding: utf-8 -*-

from __future__ import unicode_literals

from collections import Iterable
from distutils.version import StrictVersion

import json
import django

from django import forms
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.core import validators
from django.db import models
from django.utils import six
from django.utils.encoding import force_text
from django.utils.translation import ugettext_lazy as _


TYPES = {
    "int": int,
    "smallint": int,
    "bigint": int,
    "text": force_text,
    "double precision": float,
    "varchar": force_text,
}


def _cast_to_unicode(data):
    if isinstance(data, (list, tuple)):
        return [_cast_to_unicode(x) for x in data]
    elif isinstance(data, str):
        return force_text(data)
    return data


def _cast_to_type(data, type_cast):
    if isinstance(data, (list, tuple)):
        return [_cast_to_type(x, type_cast) for x in data]
    if type_cast == str:
        return force_text(data)
    return type_cast(data)


def _unserialize(value):
    if not isinstance(value, six.string_types):
        return _cast_to_unicode(value)
    try:
        return _cast_to_unicode(json.loads(value))
    except ValueError:
        return _cast_to_unicode(value)


class ArrayField(models.Field):
    empty_strings_allowed = False

    def __init__(self, dbtype="int", type_cast=None, dimension=1, *args, **kwargs):
        self._array_type = dbtype
        type_key = self._array_type.split("(")[0]

        self._explicit_type_cast = False
        if type_cast is not None:
            self._type_cast = type_cast
            self._explicit_type_cast = True
        elif type_key in TYPES:
            self._type_cast = TYPES[type_key]
        else:
            self._type_cast = lambda x: x

        self._dimension = dimension
        kwargs.setdefault("blank", True)
        kwargs.setdefault("null", True)
        kwargs.setdefault("default", None)
        super(ArrayField, self).__init__(*args, **kwargs)

    def get_db_prep_lookup(self, lookup_type, value, connection, prepared=False):
        if lookup_type == "contains":
            return [self.get_prep_value(value)]
        return super(ArrayField, self).get_db_prep_lookup(lookup_type, value, connection, prepared)

    def formfield(self, **params):
        params.setdefault("form_class", ArrayFormField)
        params.setdefault("choices_form_class", forms.TypedMultipleChoiceField)

        if self.choices:
            params.setdefault("choices", self.get_choices(include_blank=False))
            params.setdefault("coerce", self._type_cast)

        return super(ArrayField, self).formfield(**params)

    def get_db_prep_value(self, value, connection, prepared=False):
        value = value if prepared else self.get_prep_value(value)
        if not value or isinstance(value, six.string_types):
            return value
        return _cast_to_type(value, self._type_cast)

    def get_prep_value(self, value):
        return value if isinstance(value, (six.string_types, list,)) or not isinstance(value, Iterable) else list(value)

    def to_python(self, value):
        return _unserialize(value)

    def value_to_string(self, obj):
        value = self._get_val_from_obj(obj)
        return json.dumps(self.get_prep_value(value),
                          cls=DjangoJSONEncoder)

    def validate(self, value, model_instance):
        if value is None and not self.null:
            raise ValidationError(self.error_messages['null'])

        if not self.blank and value in validators.EMPTY_VALUES:
            raise ValidationError(self.error_messages['blank'])

        for val in value:
            super(ArrayField, self).validate(val, model_instance)

    def deconstruct(self):
        name, path, args, kwargs = super(ArrayField, self).deconstruct()
        if self._array_type != "int":
            kwargs["dbtype"] = self._array_type
        if self._dimension != 1:
            kwargs["dimension"] = self._dimension
        if self._explicit_type_cast:
            kwargs["type_cast"] = self._type_cast
        if self.blank:
            kwargs.pop("blank", None)
        else:
            kwargs["blank"] = self.blank
        if self.null:
            kwargs.pop("null", None)
        else:
            kwargs["null"] = self.null
        if self.default is None:
            kwargs.pop("default", None)
        else:
            kwargs["default"] = self.default

        return name, path, args, kwargs

    def db_type(self, connection):
        return "{0}{1}".format(self._array_type, "[]" * self._dimension)

    def get_transform(self, name):
        transform = super(ArrayField, self).get_transform(name)

        if transform:
            return transform
        try:
            index = int(name)
        except ValueError:
            pass
        else:
            index += 1  # postgres uses 1-indexing
            return IndexTransformFactory(index, self)
        try:
            start, end = name.split("_")
            start = int(start) + 1
            end = int(end)  # don't add one here because postgres slices are weird
        except ValueError:
            pass
        else:
            return SliceTransformFactory(start, end)


class IntegerArrayField(ArrayField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("dbtype", "int")
        super(IntegerArrayField, self).__init__(*args, **kwargs)


class SmallIntegerArrayField(ArrayField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("dbtype", "smallint")
        super(SmallIntegerArrayField, self).__init__(*args, **kwargs)


class BigIntegerArrayField(ArrayField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("dbtype", "bigint")
        super(BigIntegerArrayField, self).__init__(*args, **kwargs)


class TextArrayField(ArrayField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("dbtype", "text")
        super(TextArrayField, self).__init__(*args, **kwargs)


class FloatArrayField(ArrayField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("dbtype", "double precision")
        super(FloatArrayField, self).__init__(*args, **kwargs)


class DateArrayField(ArrayField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("dbtype", "date")
        super(DateArrayField, self).__init__(*args, **kwargs)


class DateTimeArrayField(ArrayField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("dbtype", "timestamp with time zone")
        super(DateTimeArrayField, self).__init__(*args, **kwargs)


class ArrayFormField(forms.Field):
    default_error_messages = {
        "invalid": _("Enter a list of values, joined by commas.  E.g. \"a,b,c\"."),
    }

    def __init__(self, max_length=None, min_length=None, delim=None,
                 strip=True, *args, **kwargs):
        if delim is not None:
            self.delim = delim
        else:
            self.delim = u","

        self.strip = strip

        super(ArrayFormField, self).__init__(*args, **kwargs)

    def clean(self, value):
        if not value:
            return []

        # If Django already parsed value to list
        if isinstance(value, list):
            return value

        try:
            value = value.split(self.delim)
            if self.strip:
                value = [x.strip() for x in value]
        except Exception:
            raise ValidationError(self.error_messages["invalid"])

        return value

    def prepare_value(self, value):
        if isinstance(value, (list, tuple)):  # if blank list/tuple return ''
            return self.delim.join(force_text(v) for v in value)
        return super(ArrayFormField, self).prepare_value(value)

    def to_python(self, value):
        if value is None or value == u"":
            return []
        return value.split(self.delim)


class ContainsLookup(models.Lookup):
    lookup_name = "contains"

    def as_sql(self, qn, connection):
        lhs, lhs_params = self.process_lhs(qn, connection)
        rhs, rhs_params = self.process_rhs(qn, connection)
        params = lhs_params + rhs_params
        var = "%s @> %s" % (lhs, rhs), params
        return var


class ContainedByLookup(models.Lookup):
    lookup_name = "contained_by"

    def as_sql(self, qn, connection):
        lhs, lhs_params = self.process_lhs(qn, connection)
        rhs, rhs_params = self.process_rhs(qn, connection)
        params = lhs_params + rhs_params
        return "%s <@ %s" % (lhs, rhs), params


class OverlapLookup(models.Lookup):
    lookup_name = "overlap"

    def as_sql(self, qn, connection):
        lhs, lhs_params = self.process_lhs(qn, connection)
        rhs, rhs_params = self.process_rhs(qn, connection)
        params = lhs_params + rhs_params
        return "%s && %s" % (lhs, rhs), params


class ArrayLenTransform(models.Transform):
    lookup_name = "len"

    @property
    def output_type(self):
        return models.IntegerField()

    def as_sql(self, qn, connection):
        lhs, params = qn.compile(self.lhs)
        return "array_length(%s, 1)" % lhs, params


class AnyBaseLookup(models.Lookup):
    comparator = "="
    """self.comparator holds the comparison operator to be applied to the condition"""

    def as_sql(self, qn, connection):
        """
        Basically, the array gets split up into rows (unnested) such that we can apply string comparators on the
        array's contents. Once these operations have been applied, the resulting set of PKs is used to identify,
        for what rows the given condition is true.
        :param qn: The SQLCompiler object used for compiling this query
        :param connection: A DatabaseWrapper object
        :return: a tuple (condition_string, parameter)
        """
        lhs, lhs_params = self.process_lhs(qn, connection)
        rhs, rhs_params = self.process_rhs(qn, connection)
        params = lhs_params + rhs_params
        table = self.lhs.alias
        pk_name = qn.query.model._meta.pk.name
        table_dot_pk_name = "%s.%s" % (table, pk_name)
        return "{table_dot_pk_name} IN (" \
               "SELECT DISTINCT tmp_table.{pk_name} " \
               "FROM {table} AS tmp_table " \
               "JOIN ( " \
               "SELECT tmp_table2.{pk_name} AS id, unnest({arrayfield_name}::text[]) AS unnest " \
               "FROM {table} AS tmp_table2) AS embedded_table ON embedded_table.{pk_name}=tmp_table.{pk_name} " \
               "WHERE embedded_table.unnest {comparator} %s)".format(table_dot_pk_name=table_dot_pk_name,
                                                                     pk_name=pk_name, table=table,
                                                                     arrayfield_name=lhs,
                                                                     comparator=self.comparator) % (
                   rhs, ), params


class AnyStartswithLookup(AnyBaseLookup):
    lookup_name = "any_startswith"
    comparator = "LIKE"

    def process_rhs(self, qn, connection):
        wildcarded_rhs_params = []
        rhs, rhs_params = super(AnyStartswithLookup, self).process_rhs(qn, connection)
        for param in rhs_params:
            param = "%s%%" % param
            wildcarded_rhs_params.append(param)
        return rhs, wildcarded_rhs_params


class AnyIStartswithLookup(AnyStartswithLookup):
    lookup_name = "any_istartswith"
    comparator = "ILIKE"


class AnyEndswithLookup(AnyBaseLookup):
    lookup_name = "any_endswith"
    comparator = "LIKE"

    def process_rhs(self, qn, connection):
        wildcarded_rhs_params = []
        rhs, rhs_params = super(AnyEndswithLookup, self).process_rhs(qn, connection)
        for param in rhs_params:
            param = "%%%s" % param
            wildcarded_rhs_params.append(param)
        return rhs, wildcarded_rhs_params


class AnyIEndswithLookup(AnyEndswithLookup):
    lookup_name = "any_iendswith"
    comparator = "ILIKE"


class AnyContainsLookup(AnyBaseLookup):
    lookup_name = "any_contains"
    comparator = "LIKE"

    def process_rhs(self, qn, connection):
        wildcarded_rhs_params = []
        rhs, rhs_params = super(AnyContainsLookup, self).process_rhs(qn, connection)
        for param in rhs_params:
            param = "%%%s%%" % param
            wildcarded_rhs_params.append(param)
        return rhs, wildcarded_rhs_params


class AnyIContainsLookup(AnyContainsLookup):
    lookup_name = "any_icontains"
    comparator = "ILIKE"

ArrayField.register_lookup(ContainedByLookup)
ArrayField.register_lookup(ContainsLookup)
ArrayField.register_lookup(OverlapLookup)
ArrayField.register_lookup(ArrayLenTransform)
ArrayField.register_lookup(AnyStartswithLookup)
ArrayField.register_lookup(AnyIStartswithLookup)
ArrayField.register_lookup(AnyEndswithLookup)
ArrayField.register_lookup(AnyIEndswithLookup)
ArrayField.register_lookup(AnyContainsLookup)
ArrayField.register_lookup(AnyIContainsLookup)

if StrictVersion(django.get_version()) < StrictVersion('1.9'):
    class IndexTransform(models.Transform):
        def __init__(self, index, field, *args, **kwargs):
            super(IndexTransform, self).__init__(*args, **kwargs)
            self.index = index
            self.field = field

        def as_sql(self, qn, connection):
            lhs, params = qn.compile(self.lhs)
            return "%s[%s]" % (lhs, self.index), params
else:
    class IndexTransform(models.Transform):
        def __init__(self, index, field, *args, **kwargs):
            super(IndexTransform, self).__init__(*args, output_field=field, **kwargs)
            self.index = index

        def as_sql(self, qn, connection):
            lhs, params = qn.compile(self.lhs)
            return "%s[%s]" % (lhs, self.index), params

        # TODO: Temporary not supported nested index lookup
        # @property
        # def output_type(self):
        # output_type = self.field.__class__(dimension=self.field._dimension-1)
        # output_type._array_type = self.field._array_type
        # output_type._explicit_type_cast = self.field._explicit_type_cast
        # output_type._type_cast = self.field._type_cast
        # output_type.set_attributes_from_name(self.field.name)
        # return output_type

class SliceTransform(models.Transform):
    def __init__(self, start, end, *args, **kwargs):
        super(SliceTransform, self).__init__(*args, **kwargs)
        self.start = start
        self.end = end

    def as_sql(self, qn, connection):
        lhs, params = qn.compile(self.lhs)
        return "%s[%s:%s]" % (lhs, self.start, self.end), params

class IndexTransformFactory(object):
    def __init__(self, index, field):
        self.index = index
        self.field = field

    def __call__(self, *args, **kwargs):
        return IndexTransform(self.index, self.field, *args, **kwargs)

class SliceTransformFactory(object):
    def __init__(self, start, end):
        self.start = start
        self.end = end

    def __call__(self, *args, **kwargs):
        return SliceTransform(self.start, self.end, *args, **kwargs)
