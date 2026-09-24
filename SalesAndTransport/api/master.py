from typing import Any

from django.db import transaction
from django.forms.models import model_to_dict
from django.shortcuts import get_object_or_404
from ninja import Router

from StockPassCore.auth.permissions import OwnerAdminAuth
from SalesAndTransport.models import (
    Broker,
    BusinessClient,
    Commodity,
    Transporter,
)

from SalesAndTransport.schemas.master import (
    MasterAddUpdateSchema,
    MasterGetDeleteSchema,
    MasterListSchema,
    MasterSearchSchema,
)


router = Router(auth=OwnerAdminAuth())


# =========================================================
# ENTITY CONFIGURATION
# =========================================================

ENTITY_MODELS = {
    "broker": Broker,
    "businessclient": BusinessClient,
    "commodity": Commodity,
    "transporter": Transporter,
}


ENTITY_FIELDS = {
    "broker": {
        "name",
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

    "transporter": {
        "name",
    },
}


FILTER_FIELDS = {
    "broker": {
        "name",
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

    "transporter": {
        "name",
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

    return data


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

@router.post("/add")
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

        model = get_model(entity)

        instance = model(
            **content,
            c_by=request.auth,
        )

        instance.full_clean()
        instance.save()

        return {
            "success": True,
            "message": f"{entity} created successfully.",
            "entity" : data.entity,
            "data": serialize_instance(instance),
        }

    except ValueError as e:
        return 400, {
            "success": False,
            "message": str(e),
        }

    except Exception as e:
        return 400, {
            "success": False,
            "message": str(e),
        }


# =========================================================
# UPDATE
# =========================================================

@router.patch("/upd")
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

        return {
            "success": True,
            "message": f"{entity} updated successfully.",
            "entity" : data.entity,
            "data": serialize_instance(instance),
        }

    except ValueError as e:
        return 400, {
            "success": False,
            "message": str(e),
        }

    except Exception as e:
        return 400, {
            "success": False,
            "message": str(e),
        }


# =========================================================
# GET
# =========================================================

@router.get("/get")
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

@router.delete("/del")
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

@router.post("/lst")
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
# SEARCH
# =========================================================

@router.post("/search")
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