import base64
import binascii
import logging
from io import BytesIO
from typing import Any
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.forms.models import model_to_dict
from django.forms import ImageField
from django.shortcuts import get_object_or_404
from ninja import Router
from PIL import Image, ImageOps

from StockPassCore.auth.permissions import OwnerAdminAuth
from SalesAndTransport.models import (
    Broker,
    BusinessClient,
    BusinessClientProfilePicture,
    Commodity,
    Labour,
    Tempo,
    Transporter,
)

from SalesAndTransport.schemas.master import (
    MasterAddUpdateSchema,
    MasterGetDeleteSchema,
    MasterListSchema,
    MasterSelectSchema,
    MasterSearchSchema,
)


router = Router(auth=OwnerAdminAuth())
logger = logging.getLogger("ninja")


# =========================================================
# ENTITY CONFIGURATION
# =========================================================

ENTITY_MODELS = {
    "broker": Broker,
    "businessclient": BusinessClient,
    "commodity": Commodity,
    "labour": Labour,
    "tempo": Tempo,
    "transporter": Transporter,
}


ENTITY_FIELDS = {
    "broker": {
        "name",
        "phone_number",
        "city",
        "notes",
        ""
    },

    "businessclient": {
        "name",
        "address",
        "city",
        "pincode",
        "maan_no",
        "type",
        "flag",
        "location_url",
        "profile_picture",
        "notes",
    },

    "commodity": {
        "name",
        "type",
        "bill_hammali",
        "mandi_hammali",
        "fill_qty",
        "notes",
    },

    "labour": {
        "name",
        "phone_number",
        "notes",
    },

    "tempo": {
        "name",
        "phone_number",
        "notes",
    },

    "transporter": {
        "name",
        "agency",
        "phone_number",
        "transaction_type",
        "account_number",
        "account_name",
        "ifsc_code",
        "bank",
        "branch",
        "email",
        "city",
        "notes",
    },
}


FILTER_FIELDS = {
    "broker": {
        "name",
        "city",
    },

    "businessclient": {
        "name",
        "address",
        "city",
        "pincode",
        "type",
        "flag",
    },

    "commodity": {
        "name",
        "type",
    },

    "labour": {
        "name",
    },

    "tempo": {
        "name",
    },

    "transporter": {
        "name",
        "agency",
        "city",
    },
}


# =========================================================
# HELPERS
# =========================================================

def get_model(entity: str):
    model = ENTITY_MODELS.get(entity)

    if not model:
        raise ValueError(f"Unsupported entity: {entity}")

    return model


def validate_content(entity: str, content: dict[str, Any]):
    allowed_fields = ENTITY_FIELDS[entity]

    invalid_fields = set(content.keys()) - allowed_fields

    if invalid_fields:
        raise ValueError(
            f"Invalid field(s) for {entity}: "
            f"{', '.join(sorted(invalid_fields))}"
        )


def validate_filters(entity: str, filters: dict[str, Any]):
    allowed_fields = FILTER_FIELDS[entity]

    invalid_fields = set(filters.keys()) - allowed_fields

    if invalid_fields:
        raise ValueError(
            f"Invalid filter field(s) for {entity}: "
            f"{', '.join(sorted(invalid_fields))}"
        )


def resize_profile_picture(image_content: bytes, image_format: str) -> bytes:
    output = BytesIO()
    with Image.open(BytesIO(image_content)) as source_image:
        image = ImageOps.exif_transpose(source_image)
        image = ImageOps.fit(
            image,
            (256, 256),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )

        if image_format == "JPEG" and image.mode not in ("RGB", "L", "CMYK"):
            image = image.convert("RGB")

        image.save(output, format=image_format)

    return output.getvalue()


def profile_picture_storage_path(picture_url: str) -> str | None:
    media_url = urlsplit(settings.MEDIA_URL)
    picture_url_parts = urlsplit(picture_url)

    if media_url.netloc and (
        picture_url_parts.scheme != media_url.scheme
        or picture_url_parts.netloc != media_url.netloc
    ):
        return None

    media_path = f"{media_url.path.rstrip('/')}/"
    picture_path = unquote(picture_url_parts.path)
    if not picture_path.startswith(media_path):
        return None

    storage_path = picture_path[len(media_path):]
    path_parts = storage_path.split("/")
    if (
        len(path_parts) != 2
        or path_parts[0] != "profile_picture"
        or not path_parts[1]
        or "\\" in storage_path
    ):
        return None

    return storage_path


def serialize_instance(instance):
    excluded_fields = {
        "is_active",
        "c_by",
        "c_at",
        "m_by",
        "m_at",
        "d_at",
        "d_by",
    }

    data = {
        "id": instance.id,
    }

    for field in instance._meta.fields:

        if field.name in excluded_fields:
            continue

        value = getattr(instance, field.name)

        if field.is_relation:
            data[field.name] = (
                value.id if value is not None else None
            )
        else:
            data[field.name] = value

    if isinstance(instance, BusinessClient):
        data["profile_picture"] = (
            instance.profile_pictures.filter(is_active=True)
            .order_by("-id")
            .values_list("url", flat=True)
            .first()
        )

    return data


def prepare_profile_picture(value: Any):
    if not isinstance(value, str):
        raise ValueError("profile_picture must be a base64 string.")

    encoded_image = value
    if value.startswith("data:"):
        header, separator, encoded_image = value.partition(",")
        if (
            not separator
            or not header.lower().startswith("data:image/")
            or ";base64" not in header.lower()
        ):
            raise ValueError("profile_picture must contain a base64 image.")

    try:
        image_content = base64.b64decode(encoded_image, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("profile_picture is not valid base64.") from error

    if not image_content:
        raise ValueError("profile_picture cannot be empty.")

    try:
        image = ImageField().clean(
            SimpleUploadedFile("profile_picture.jpg", image_content)
        )
    except ValidationError as error:
        raise ValueError("profile_picture must be a valid image.") from error

    image_format = image.image.format
    extension = next(
        (
            suffix.lstrip(".")
            for suffix, registered_format in Image.registered_extensions().items()
            if registered_format == image_format
        ),
        None,
    )
    if extension is None:
        raise ValueError("profile_picture uses an unsupported image format.")

    image_content = resize_profile_picture(image_content, image_format)
    return image_content, extension


def save_profile_picture(request, business_client, image_data):
    image_content, extension = image_data
    storage_path = f"profile_picture/{uuid4().hex}.{extension}"
    saved_path = default_storage.save(storage_path, ContentFile(image_content))
    old_storage_path = None

    try:
        picture = (
            business_client.profile_pictures.filter(is_active=True)
            .order_by("-id")
            .first()
        )
        if picture is None:
            picture = BusinessClientProfilePicture(
                business_client=business_client,
                c_by=request.auth,
            )

        if picture.pk:
            old_storage_path = profile_picture_storage_path(picture.url)

        picture.url = request.build_absolute_uri(default_storage.url(saved_path))
        picture.m_by = request.auth
        picture.save()
    except Exception:
        default_storage.delete(saved_path)
        raise

    if old_storage_path and old_storage_path != saved_path:
        transaction.on_commit(
            lambda path=old_storage_path: default_storage.delete(path)
        )


def paginate_queryset(queryset, page: int, page_size: int):

    if page < 1:
        raise ValueError("page must be >= 1")

    if page_size < 1:
        raise ValueError("page_size must be >= 1")

    if page_size > 100:
        raise ValueError("page_size cannot be greater than 100")

    total = queryset.count()

    start = (page - 1) * page_size
    end = start + page_size

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
        "results": [
            serialize_instance(obj)
            for obj in queryset[start:end]
        ],
    }


# =========================================================
# ADD
# =========================================================

@router.post("/add/", response={200: dict, 400: dict})
@transaction.atomic
def add_entity(request, data: MasterAddUpdateSchema):

    if data.id is not None:
        return 400, {
            "success": False,
            "message": "id must be null when adding an entity.",
        }

    entity = data.entity
    content = data.content.copy()

    try:
        validate_content(entity, content)
        profile_picture = content.pop("profile_picture", None)
        image_data = (
            prepare_profile_picture(profile_picture)
            if profile_picture is not None
            else None
        )

        model = get_model(entity)

        instance = model(
            **content,
            c_by=request.auth,
        )

        instance.full_clean()
        instance.save()

        if image_data is not None:
            save_profile_picture(request, instance, image_data)

        return {
            "success": True,
            "message": f"{entity} created successfully.",
            "entity" : data.entity,
            "data": serialize_instance(instance),
        }

    except ValueError as e:
        transaction.set_rollback(True)
        return 400, {
            "success": False,
            "message": str(e),
        }

    except Exception as e:
        transaction.set_rollback(True)
        if settings.DEBUG:
            logger.exception("Master entity request failed")
        return 400, {
            "success": False,
            "message": str(e),
        }


# =========================================================
# UPDATE
# =========================================================

@router.patch("/upd/", response={200: dict, 400: dict})
@transaction.atomic
def update_entity(request, data: MasterAddUpdateSchema):

    if data.id is None:
        return 400, {
            "success": False,
            "message": "id is required when updating an entity.",
        }

    entity = data.entity
    content = data.content.copy()

    try:
        validate_content(entity, content)
        profile_picture = content.pop("profile_picture", None)
        image_data = (
            prepare_profile_picture(profile_picture)
            if profile_picture is not None
            else None
        )

        model = get_model(entity)

        # Only active records can be updated.
        instance = get_object_or_404(
            model,
            id=data.id,
            is_active=True,
        )

        for field, value in content.items():
            setattr(instance, field, value)

        instance.m_by = request.auth

        instance.full_clean()
        instance.save()

        if image_data is not None:
            save_profile_picture(request, instance, image_data)

        return {
            "success": True,
            "message": f"{entity} updated successfully.",
            "entity" : data.entity,
            "data": serialize_instance(instance),
        }

    except ValueError as e:
        transaction.set_rollback(True)
        return 400, {
            "success": False,
            "message": str(e),
        }

    except Exception as e:
        transaction.set_rollback(True)
        if settings.DEBUG:
            logger.exception("Master entity request failed")
        return 400, {
            "success": False,
            "message": str(e),
        }


# =========================================================
# GET
# =========================================================

@router.get("/get/", response={200: dict, 400: dict})
def get_entity(request, data: MasterGetDeleteSchema):

    try:
        model = get_model(data.entity)

        # Only active records can be fetched.
        instance = get_object_or_404(
            model,
            id=data.id,
            is_active=True,
        )

        return {
            "success": True,
            "entity" : data.entity,
            "data": serialize_instance(instance),
        }

    except ValueError as e:
        return 400, {
            "success": False,
            "message": str(e),
        }


# =========================================================
# DELETE
# =========================================================

@router.delete("/del/", response={200: dict, 400: dict})
@transaction.atomic
def delete_entity(request, data: MasterGetDeleteSchema):

    try:
        model = get_model(data.entity)

        # Only active records can be deleted.
        instance = get_object_or_404(
            model,
            id=data.id,
            is_active=True,
        )

        instance.is_active = False
        instance.d_by = request.auth

        instance.save(
            update_fields=[
                "is_active",
                "d_by",
            ]
        )

        return {
            "success": True,
            "message": f"{data.entity} deleted successfully.",
            "entity" : data.entity,
            "id": instance.id,
        }

    except ValueError as e:
        return 400, {
            "success": False,
            "message": str(e),
        }


# =========================================================
# LIST
# =========================================================

@router.post("/lst/", response={200: dict, 400: dict})
def list_entities(request, data: MasterListSchema):

    try:
        model = get_model(data.entity)

        validate_filters(
            data.entity,
            data.filters,
        )

        # ALWAYS active records only.
        queryset = model.objects.filter(
            is_active=True
        )

        if data.filters:
            queryset = queryset.filter(**data.filters)

        queryset = queryset.order_by("id")

        return {
            "success": True,
            "entity": data.entity,
            "data": paginate_queryset(
                queryset,
                data.page,
                data.page_size,
            ),
        }

    except ValueError as e:
        return 400, {
            "success": False,
            "message": str(e),
        }


# =========================================================
# SELECT
# =========================================================

@router.post("/sel/", response={200: dict, 400: dict})
def select_entities(request, data: MasterSelectSchema):

    try:
        model = get_model(data.entity)

        validate_filters(
            data.entity,
            data.filters,
        )

        queryset = model.objects.filter(
            is_active=True
        )

        if data.filters:
            queryset = queryset.filter(**data.filters)

        queryset = queryset.order_by("id").values("id", "name")

        return {
            "success": True,
            "entity": data.entity,
            "data": list(queryset),
        }

    except ValueError as e:
        return 400, {
            "success": False,
            "message": str(e),
        }


# =========================================================
# SEARCH
# =========================================================

@router.post("/search/", response={200: dict, 400: dict})
def search_entities(request, data: MasterSearchSchema):

    try:
        model = get_model(data.entity)

        validate_filters(
            data.entity,
            data.filters,
        )

        # ALWAYS active records only.
        queryset = model.objects.filter(
            is_active=True,
            name__icontains=data.search.strip(),
        )

        if data.filters:
            queryset = queryset.filter(**data.filters)

        queryset = queryset.order_by("name", "id")

        return {
            "success": True,
            "entity": data.entity,
            "search": data.search,
            "total": queryset.count(),
            "results": [
                serialize_instance(obj)
                for obj in queryset
            ],
        }

    except ValueError as e:
        return 400, {
            "success": False,
            "message": str(e),
        }
