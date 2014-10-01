# -*- coding: utf-8 -*-


import unittest
import datetime
from django.contrib.admin import AdminSite
from django.contrib.admin import ModelAdmin
from django.core.serializers import serialize
from django.core.serializers import deserialize
from django.db import connection
from django.test import TestCase
from django.utils.encoding import force_text
from django.utils import six
from django import forms
import django

from djorm_pgarray.fields import ArrayField
from djorm_pgarray.fields import ArrayFormField
from .forms import IntArrayForm
from .models import IntModel
from .models import TextModel
from .models import DoubleModel
from .models import MTextModel
from .models import MultiTypeModel
from .models import ChoicesModel
from .models import Item
from .models import Item2
from .models import DateModel
from .models import DateTimeModel
from .models import MacAddrModel
from .models import BytesArrayModel


# Adapters

class MacAddr(six.text_type):
    pass


def custom_type_cast(val):
    return val


def get_type_oid(sql_expression):
    """Query the database for the OID of the type of sql_expression."""
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT " + sql_expression)
        return cursor.description[0][1]
    finally:
        cursor.close()


def cast_macaddr(val, cur):
    return MacAddr(val)


def adapt_macaddr(maddr):
    from psycopg2.extensions import adapt, AsIs

    return AsIs("{0}::macaddr".format(adapt(str(maddr))))


def register_macaddr_type():
    from psycopg2.extensions import register_adapter, new_type, register_type, new_array_type
    import psycopg2

    oid = get_type_oid("NULL::macaddr")
    PGTYPE = new_type((oid,), "macaddr", cast_macaddr)
    register_type(PGTYPE)
    register_adapter(MacAddr, adapt_macaddr)

    mac_array_oid = get_type_oid("'{}'::macaddr[]")
    array_of_mac = new_array_type((mac_array_oid, ), 'macaddr', psycopg2.STRING)
    psycopg2.extensions.register_type(array_of_mac)


# Tests

class ArrayFieldTests(TestCase):
    def setUp(self):
        IntModel.objects.all().delete()
        TextModel.objects.all().delete()
        DoubleModel.objects.all().delete()
        MultiTypeModel.objects.all().delete()

    def test_default_value(self):
        """Test default value on model is created."""
        obj = Item.objects.create()
        self.assertEqual(obj.tags, [])

        obj = Item2.objects.create()
        self.assertEqual(obj.tags, [])

        obj = IntModel.objects.create()
        self.assertEqual(obj.field, None)

    def test_date(self):
        """Test date array fields."""
        d = datetime.date(2011, 11, 11)
        instance = DateModel.objects.create(dates=[d])

        instance = DateModel.objects.get(pk=instance.pk)
        self.assertEqual(instance.dates[0], d)

    def test_datetime(self):
        d = datetime.datetime(2011, 11, 11, 11, 11, 11)
        instance = DateTimeModel.objects.create(dates=[d])
        instance = DateTimeModel.objects.get(pk=instance.pk)
        self.assertEqual(instance.dates[0], d)

    def test_empty_create(self):
        instance = IntModel.objects.create(field=[])
        instance = IntModel.objects.get(pk=instance.pk)
        self.assertEqual(instance.field, [])

    def test_macaddr_model(self):
        register_macaddr_type()
        instance = MacAddrModel.objects.create()
        instance.field = [MacAddr('00:24:d6:54:ff:c6'), MacAddr('00:24:d6:54:ff:c4')]
        instance.save()

        instance = MacAddrModel.objects.get(pk=instance.pk)
        self.assertEqual(instance.field, ['00:24:d6:54:ff:c6', '00:24:d6:54:ff:c4'])

    def test_correct_behavior_with_text_arrays_01(self):
        obj = TextModel.objects.create(field=[[1, 2], [3, 4]])
        obj = TextModel.objects.get(pk=obj.pk)
        self.assertEqual(obj.field, [[u'1', u'2'], [u'3', u'4']])

    def test_correct_behavior_with_text_arrays_02(self):
        obj = MTextModel.objects.create(data=[[u"1", u"2"], [u"3", u"ñ"]])
        obj = MTextModel.objects.get(pk=obj.pk)
        self.assertEqual(obj.data, [[u"1", u"2"], [u"3", u"ñ"]])

    def test_correct_behavior_with_int_arrays(self):
        obj = IntModel.objects.create(field=[1, 2, 3])
        obj = IntModel.objects.get(pk=obj.pk)
        self.assertEqual(obj.field, [1, 2, 3])

    def test_correct_behavior_with_float_arrays(self):
        obj = DoubleModel.objects.create(field=[1.2, 2.4, 3])
        obj = DoubleModel.objects.get(pk=obj.pk)
        self.assertEqual(obj.field, [1.2, 2.4, 3])

    def test_value_to_string_serializes_correctly(self):
        obj = MTextModel.objects.create(data=[[u"1", u"2"], [u"3", u"ñ"]])
        obj_int = IntModel.objects.create(field=[1, 2, 3])

        serialized_obj = serialize('json', MTextModel.objects.filter(pk=obj.pk))
        serialized_obj_int = serialize('json', IntModel.objects.filter(pk=obj_int.pk))

        obj.delete()
        obj_int.delete()

        deserialized_obj = list(deserialize('json', serialized_obj))[0]
        deserialized_obj_int = list(deserialize('json', serialized_obj_int))[0]

        obj = deserialized_obj.object
        obj_int = deserialized_obj_int.object
        obj.save()
        obj_int.save()

        self.assertEqual(obj.data, [[u"1", u"2"], [u"3", u"ñ"]])
        self.assertEqual(obj_int.field, [1, 2, 3])

    def test_to_python_serializes_xml_correctly(self):
        obj = MTextModel.objects.create(data=[[u"1", u"2"], [u"3", u"ñ"]])
        obj_int = IntModel.objects.create(field=[1, 2, 3])

        serialized_obj = serialize('xml', MTextModel.objects.filter(pk=obj.pk))
        serialized_obj_int = serialize('xml', IntModel.objects.filter(pk=obj_int.pk))

        obj.delete()
        obj_int.delete()
        deserialized_obj = list(deserialize('xml', serialized_obj))[0]
        deserialized_obj_int = list(deserialize('xml', serialized_obj_int))[0]
        obj = deserialized_obj.object
        obj_int = deserialized_obj_int.object
        obj.save()
        obj_int.save()

        self.assertEqual(obj.data, [[u"1", u"2"], [u"3", u"ñ"]])
        self.assertEqual(obj_int.field, [1, 2, 3])

    def test_can_override_formfield(self):
        model_field = ArrayField()

        class FakeFieldClass(object):
            def __init__(self, *args, **kwargs):
                pass

        form_field = model_field.formfield(form_class=FakeFieldClass)
        self.assertIsInstance(form_field, FakeFieldClass)

    if django.VERSION[:2] >= (1, 6):
        def test_default_formfield_with_choices(self):
            model_field = ArrayField(choices=[('a', 'a')], dbtype='text')
            form_field = model_field.formfield()
            self.assertIsInstance(form_field, forms.TypedMultipleChoiceField)
            self.assertEqual(form_field.choices, [('a', 'a')])
            self.assertEqual(form_field.coerce, force_text)

    def test_other_types_properly_casted(self):
        obj = MultiTypeModel.objects.create(
            smallints=[1, 2, 3],
            varchars=['One', 'Two', 'Three']
        )
        obj = MultiTypeModel.objects.get(pk=obj.pk)

        self.assertEqual(obj.smallints, [1, 2, 3])
        self.assertEqual(obj.varchars, ['One', 'Two', 'Three'])

    def test_custom_bytes_field(self):
        data = [memoryview(b'\x01\x00\x00\x00\x00\x00'),
                memoryview(b'\x02\x00\x00\x00\x00\x00'),
                memoryview(b'\x03\x00\x00\x00\x00\x00')]

        obj = BytesArrayModel()
        obj.entries = data
        obj.save()

        obj2 = BytesArrayModel.objects.get(pk=obj.pk)

        # This is so, because python2/3 inconsistences
        # With python3 psycopg2 returns memoryviews, with
        # python2 psycopg2 returns buffer. buffer does not exists
        # on python3, buffer and memoryview has different interfaces
        # and buffer can be casted easy to memoryview.
        self.assertEqual(memoryview(obj2.entries[0]).tobytes(), data[0].tobytes())
        self.assertEqual(memoryview(obj2.entries[1]).tobytes(), data[1].tobytes())
        self.assertEqual(memoryview(obj2.entries[2]).tobytes(), data[2].tobytes())

    def test_choices_validation(self):
        obj = ChoicesModel(choices=['A'])
        obj.full_clean()
        obj.save()


if django.VERSION[:2] >= (1, 7):
    class AdditionalArrayFieldTests(TestCase):
        def setUp(self):
            IntModel.objects.all().delete()

        def test_exact(self):
            obj = IntModel.objects.create(field=[1])
            qs = IntModel.objects.filter(field__exact=[1])
            self.assertEqual(qs.count(), 1)

        def test_isnull(self):
            obj = IntModel.objects.create(field=[1])
            obj = IntModel.objects.create(field=None)
            qs = IntModel.objects.filter(field__isnull=True)
            self.assertEqual(qs.count(), 1)

        def test_in(self):
            obj = IntModel.objects.create(field=[1])
            obj = IntModel.objects.create(field=[2])
            obj = IntModel.objects.create(field=[3])

            qs = IntModel.objects.filter(field__in=[[1], [2]])
            self.assertEqual(qs.count(), 2)

        def test_index(self):
            obj = IntModel.objects.create(field=[1, 2])
            obj = IntModel.objects.create(field=[2, 3])
            obj = IntModel.objects.create(field=[3, 4])

            qs = IntModel.objects.filter(field__0__in=[1, 2]).order_by("id")
            self.assertEqual(qs.count(), 2)
            self.assertSequenceEqual(qs[0].field, [1, 2])
            self.assertSequenceEqual(qs[1].field, [2, 3])

            qs = IntModel.objects.filter(field__0=1)
            self.assertEqual(qs.count(), 1)
            self.assertSequenceEqual(qs[0].field, [1, 2])

            # TODO: temporary not supported nested index search :(
            # obj = IntModel.objects.create(field2=[[1, 2], [3, 4]])
            # obj = IntModel.objects.create(field2=[[5, 6], [7, 8]])
            # qs = IntModel.objects.filter(field2__0__0=1)
            # self.assertEqual(qs.count(), 1)

        def test_slice(self):
            obj = IntModel.objects.create(field=[2])
            obj = IntModel.objects.create(field=[2, 3])
            obj = IntModel.objects.create(field=[5])
            obj = IntModel.objects.create(field=[6, 3])

            qs = IntModel.objects.filter(field__0_1=[2])
            self.assertEqual(qs.count(), 2)

        @unittest.expectedFailure
        def test_index_1(self):
            obj = IntModel.objects.create(field2=[[1, 2], [3, 4]])
            obj = IntModel.objects.create(field2=[[5, 6], [7, 8]])

            qs = IntModel.objects.filter(field2__0=[1, 2])
            self.assertEqual(qs.count(), 1)

        def test_len(self):
            obj = IntModel.objects.create(field=[1, 2])
            obj = IntModel.objects.create(field=[2, 3, 4])

            qs = IntModel.objects.filter(field__len__lte=2)
            self.assertEqual(qs.count(), 1)

        def test_contains_lookup(self):
            obj1 = IntModel.objects.create(field=[1, 4, 3])
            obj2 = IntModel.objects.create(field=[0, 10, 50])

            qs = IntModel.objects.filter(field__contains=[1, 3])
            self.assertEqual(qs.count(), 1)

        def test_contained_by_lookup(self):
            obj1 = IntModel.objects.create(field=[2, 7])
            obj2 = IntModel.objects.create(field=[0, 10, 50])

            qs = IntModel.objects.filter(field__contained_by=[1, 7, 4, 2, 6])
            self.assertEqual(qs.count(), 1)

        def test_overlap_lookup(self):
            obj1 = IntModel.objects.create(field=[1, 4, 3])
            obj2 = IntModel.objects.create(field=[0, 10, 50])

            qs = IntModel.objects.filter(field__overlap=[2, 1])
            self.assertEqual(qs.count(), 1)

        def test_contains_unicode(self):
            obj = TextModel.objects.create(field=[u"Fóö", u"Пример", u"test"])
            qs = TextModel.objects.filter(field__contains=[u"Пример"])
            self.assertEqual(qs.count(), 1)

        def test_deconstruct_defaults(self):
            """Attributes at default values left out of deconstruction."""
            af = ArrayField()

            name, path, args, kwargs = af.deconstruct()

            naf = ArrayField(*args, **kwargs)

            self.assertEqual((args, kwargs), ([], {}))
            self.assertEqual(af._array_type, naf._array_type)
            self.assertEqual(af._dimension, naf._dimension)
            self.assertEqual(af._type_cast, naf._type_cast)
            self.assertEqual(af.blank, naf.blank)
            self.assertEqual(af.null, naf.null)
            self.assertEqual(af.default, naf.default)

        def test_deconstruct_custom(self):
            """Attributes at custom values included in deconstruction."""
            af = ArrayField(
                dbtype='text',
                dimension=2,
                type_cast=custom_type_cast,
                blank=False,
                null=False,
                default=[['a'], ['b']],
            )

            name, path, args, kwargs = af.deconstruct()

            naf = ArrayField(*args, **kwargs)

            self.assertEqual(args, [])
            self.assertEqual(
                kwargs,
                {
                    'dbtype': 'text',
                    'dimension': 2,
                    'type_cast': custom_type_cast,
                    'blank': False,
                    'null': False,
                    'default': [['a'], ['b']],
                },
            )
            self.assertEqual(af._array_type, naf._array_type)
            self.assertEqual(af._dimension, naf._dimension)
            self.assertEqual(af._type_cast, naf._type_cast)
            self.assertEqual(af.blank, naf.blank)
            self.assertEqual(af.null, naf.null)
            self.assertEqual(af.default, naf.default)

        def test_deconstruct_unknown_dbtype(self):
            """Deconstruction does not include type_cast if dbtype unknown."""
            af = ArrayField(dbtype='foo')

            name, path, args, kwargs = af.deconstruct()

            naf = ArrayField(*args, **kwargs)

            self.assertEqual(kwargs, {'dbtype': 'foo'})

        def test_lookup_text_stubs_in_one_dimension(self):
            """
            Tests whether we're able to lookup text stubs in a simple array field
            """
            # Setting up some objects, useful for stub-querying
            tm1 = TextModel.objects.create(field=['a.v1', 'a.v2', 'b.v1'])
            tm2 = TextModel.objects.create(field=['c.v1', 'c.v2', 'b.v2'])
            tm3 = TextModel.objects.create(field=['d.1'])

            i1 = Item2.objects.create(tags=['SOME', 'CONTENT'])
            i2 = Item2.objects.create(tags=['some', 'content'])

            # Query...
            self.assertEqual(tm1, TextModel.objects.get(field__any_startswith='a'))
            self.assertEqual(tm2, TextModel.objects.get(field__any_istartswith='C'))
            self.assertEqual(2, TextModel.objects.filter(field__any_icontains='V').count())
            self.assertEqual(2, TextModel.objects.filter(field__any_endswith='2').count())

            self.assertEqual(i2, Item2.objects.get(tags__any_contains='ont'))
            self.assertEqual(2, Item2.objects.filter(tags__any_icontains='ont').count())

        def test_lookup_text_stubs_in_multiple_dimensions(self):
            """
            Tests whether we're able to lookup text stubs in more than one dimension
            """
            # Settings up an object or two...
            mtm1 = MTextModel.objects.create(data=[['this', 'is'], ['some', 'content']])
            mtm2 = MTextModel.objects.create(data=[['THIS', 'IS'], ['SOME', 'MORE']])

            # Query...
            self.assertEqual(mtm1, MTextModel.objects.get(data__any_contains='is'))
            self.assertEqual(2, MTextModel.objects.filter(data__any_icontains='is').count())


class ArrayFormFieldTests(TestCase):
    def test_regular_forms(self):
        form = IntArrayForm()
        self.assertFalse(form.is_valid())
        form = IntArrayForm({'field': u'1,2'})
        self.assertTrue(form.is_valid())

    def test_empty_value(self):
        form = IntArrayForm({'field': u''})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['field'], [])

    def test_admin_forms(self):
        site = AdminSite()
        model_admin = ModelAdmin(IntModel, site)
        form_clazz = model_admin.get_form(None)
        form_instance = form_clazz()

        try:
            form_instance.as_table()
        except TypeError:
            self.fail('HTML Rendering of the form caused a TypeError')

    def test_unicode_data(self):
        field = ArrayFormField()
        result = field.prepare_value([u"Клиент", u"こんにちは"])
        self.assertEqual(result, u"Клиент,こんにちは")

    def test_invalid_error(self):
        form = IntArrayForm({'field': 1})
        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors['field'],
            [u'Enter a list of values, joined by commas.  E.g. "a,b,c".']
        )
