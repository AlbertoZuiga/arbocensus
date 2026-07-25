import io

import factory
from apps.datasets.models import Dataset, Tree
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def observation_photo(name="obs.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), color=(0, 128, 0)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


class DatasetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Dataset

    name = factory.Sequence(lambda n: f"Dataset {n}")
    total_trees = 0


class TreeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tree

    dataset = factory.SubFactory(DatasetFactory)
    location = factory.LazyAttribute(lambda obj: Point(obj.lon, obj.lat))

    class Params:
        lon = -70.65
        lat = -33.45


class CustomUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(lambda n: f"user{n}")
    role = get_user_model().Role.SURVEYOR
