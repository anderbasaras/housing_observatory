"""Esquemas de entrada y salida de la API (Pydantic).

Pydantic valida automaticamente los datos que llegan: comprueba tipos,
rangos y valores permitidos ANTES de que lleguen al modelo. Si algo
esta mal, devuelve un error 422 claro sin que tengamos que escribirlo.
"""

from pydantic import BaseModel, Field, field_validator

from api.model_loader import (
    TIPOLOGIAS_VALIDAS,
    ZONAS_VALIDAS,
    MARGENES_VALIDOS,
)


class PeticionPrecio(BaseModel):
    """Datos de entrada para estimar el precio de un alquiler.

    El usuario NO manda sqm_per_room: la API la calcula sola a partir
    de area_sqm y n_rooms, igual que se hizo al construir el dataset.
    """
    area_sqm: float = Field(..., gt=0, description="Superficie en m2")
    n_rooms: int = Field(..., ge=1, description="Numero de habitaciones (minimo 1)")
    typology_grouped: str = Field(..., description="flat, penthouse u other")
    zona_modelo: str = Field(..., description="Zona en formato Municipio|Barrio")
    river_bank: str = Field(..., description="Margen de la ria")

    # Los validadores comprueban que los valores categoricos existan
    # en el conjunto con el que se entreno el modelo. Si no, error claro.
    @field_validator("typology_grouped")
    @classmethod
    def _val_tipologia(cls, v):
        if v not in TIPOLOGIAS_VALIDAS:
            raise ValueError(
                f"tipologia no valida: {v}. Validas: {sorted(TIPOLOGIAS_VALIDAS)}"
            )
        return v

    @field_validator("zona_modelo")
    @classmethod
    def _val_zona(cls, v):
        if v not in ZONAS_VALIDAS:
            raise ValueError(
                f"zona no valida: {v}. Hay {len(ZONAS_VALIDAS)} zonas validas "
                f"(ver el endpoint /zonas)."
            )
        return v

    @field_validator("river_bank")
    @classmethod
    def _val_margen(cls, v):
        if v not in MARGENES_VALIDOS:
            raise ValueError(
                f"margen no valido: {v}. Validos: {sorted(MARGENES_VALIDOS)}"
            )
        return v


class RespuestaPrecio(BaseModel):
    """Respuesta del endpoint de prediccion."""
    precio_estimado_eur: float = Field(..., description="Precio mensual estimado en euros")
    sqm_per_room: float = Field(..., description="m2 por habitacion (calculado)")
