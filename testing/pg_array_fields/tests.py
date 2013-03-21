# -*- coding: utf-8 -*-

from django.test import TestCase
from django.core.serializers import serialize, deserialize

from djorm_expressions.base import SqlExpression
from .models import IntModel, TextModel, DoubleModel, MTextModel

class ArrayFieldTests(TestCase):
    def setUp(self):
        IntModel.objects.all().delete()
        TextModel.objects.all().delete()
        DoubleModel.objects.all().delete()

    def test_empty_create(self):
        instance = IntModel.objects.create(lista=[])
        instance = IntModel.objects.get(pk=instance.pk)
        self.assertEqual(instance.lista, [])

    def test_overlap(self):
        obj1 = IntModel.objects.create(lista=[1,2,3])
        obj2 = IntModel.objects.create(lista=[2,4,5])
        obj3 = IntModel.objects.create(lista=[5,33,21])

        queryset = IntModel.objects.where(
            SqlExpression("lista", "&&", [1,2,3])
        )
        self.assertEqual(queryset.count(), 2)

        queryset = IntModel.objects.where(
            SqlExpression("lista", "&&", [1,2,3])
        )
        self.assertEqual(queryset.count(), 2)

    def test_contains_unicode(self):
        obj = TextModel.objects\
            .create(lista=[u"Fóö", u"Пример", u"test"])

        queryset = TextModel.objects.where(
            SqlExpression("lista", "@>", [u"Пример"])
        )
        self.assertEqual(queryset.count(), 1)

    def test_correct_behavior_with_text_arrays_01(self):
        obj = TextModel.objects.create(lista=[[1,2],[3,4]])
        obj = TextModel.objects.get(pk=obj.pk)
        self.assertEqual(obj.lista, [[u'1', u'2'], [u'3', u'4']])

    def test_correct_behavior_with_text_arrays_02(self):
        obj = MTextModel.objects.create(data=[[u"1",u"2"],[u"3",u"ñ"]])
        obj = MTextModel.objects.get(pk=obj.pk)
        self.assertEqual(obj.data, [[u"1",u"2"],[u"3",u"ñ"]])

    def test_value_to_string_serializes_correctly(self):
        obj = MTextModel.objects.create(data=[[u"1",u"2"],[u"3",u"ñ"]])
        obj_int = IntModel.objects.create(lista=[1,2,3])

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


        self.assertEqual(obj.data, [[u"1",u"2"],[u"3",u"ñ"]])
        self.assertEqual(obj_int.lista, [1,2,3])
