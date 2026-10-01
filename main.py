from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
import sqlite3
import math


# ============================================================
# Application
# ============================================================

app = FastAPI(
    title="Address Book API",
    description="API for managing addresses and finding addresses within a given distance.",
)


# ============================================================
# Database
# ============================================================

DATABASE = "addresses.db"


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_table():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            street TEXT NOT NULL,
            city TEXT NOT NULL,
            postal_code TEXT,
            country TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL
        )
    """)

    connection.commit()
    connection.close()


create_table()


# ============================================================
# Pydantic Models
# ============================================================

class AddressCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name associated with the address"
    )

    street: str = Field(
        ...,
        min_length=1,
        max_length=200
    )

    city: str = Field(
        ...,
        min_length=1,
        max_length=100
    )

    postal_code: str | None = Field(
        default=None,
        max_length=20
    )

    country: str = Field(
        ...,
        min_length=1,
        max_length=100
    )

    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitude between -90 and 90"
    )

    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitude between -180 and 180"
    )


class Address(AddressCreate):
    id: int


# ============================================================
# Helper Functions
# ============================================================

def row_to_address(row):
    return dict(row)


# ============================================================
# CREATE ADDRESS
# ============================================================

@app.post(
    "/addresses",
    response_model=Address,
    status_code=201,
    summary="Create an address"
)
def create_address(address: AddressCreate):

    connection = get_db()

    cursor = connection.execute(
        """
        INSERT INTO addresses (
            name,
            street,
            city,
            postal_code,
            country,
            latitude,
            longitude
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            address.name,
            address.street,
            address.city,
            address.postal_code,
            address.country,
            address.latitude,
            address.longitude
        )
    )

    connection.commit()

    address_id = cursor.lastrowid

    row = connection.execute(
        "SELECT * FROM addresses WHERE id = ?",
        (address_id,)
    ).fetchone()

    connection.close()

    return row_to_address(row)


# ============================================================
# UPDATE ADDRESS
# ============================================================

@app.put(
    "/addresses/{address_id}",
    response_model=Address,
    summary="Update an address"
)
def update_address(
    address_id: int,
    address: AddressCreate
):

    connection = get_db()

    existing = connection.execute(
        "SELECT id FROM addresses WHERE id = ?",
        (address_id,)
    ).fetchone()

    if existing is None:
        connection.close()

        raise HTTPException(
            status_code=404,
            detail="Address not found"
        )

    connection.execute(
        """
        UPDATE addresses
        SET
            name = ?,
            street = ?,
            city = ?,
            postal_code = ?,
            country = ?,
            latitude = ?,
            longitude = ?
        WHERE id = ?
        """,
        (
            address.name,
            address.street,
            address.city,
            address.postal_code,
            address.country,
            address.latitude,
            address.longitude,
            address_id
        )
    )

    connection.commit()

    row = connection.execute(
        "SELECT * FROM addresses WHERE id = ?",
        (address_id,)
    ).fetchone()

    connection.close()

    return row_to_address(row)


# ============================================================
# DELETE ADDRESS
# ============================================================

@app.delete(
    "/addresses/{address_id}",
    summary="Delete an address"
)
def delete_address(address_id: int):

    connection = get_db()

    cursor = connection.execute(
        "DELETE FROM addresses WHERE id = ?",
        (address_id,)
    )

    connection.commit()
    connection.close()

    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=404,
            detail="Address not found"
        )

    return {
        "message": "Address deleted successfully"
    }


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def calculate_distance(
    latitude1,
    longitude1,
    latitude2,
    longitude2
):
    """
    Calculate distance between two coordinates
    using the Haversine formula.

    Returns distance in kilometers.
    """

    earth_radius_km = 6371.0

    lat1 = math.radians(latitude1)
    lat2 = math.radians(latitude2)

    delta_lat = math.radians(latitude2 - latitude1)
    delta_lon = math.radians(longitude2 - longitude1)

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius_km * c


# ============================================================
# FIND ADDRESSES WITHIN DISTANCE
# ============================================================

@app.get(
    "/addresses/nearby",
    summary="Find addresses within a given distance"
)
def get_nearby_addresses(
    latitude: float = Query(
        ...,
        ge=-90,
        le=90,
        description="Center latitude"
    ),

    longitude: float = Query(
        ...,
        ge=-180,
        le=180,
        description="Center longitude"
    ),

    distance_km: float = Query(
        ...,
        gt=0,
        le=20000,
        description="Maximum distance in kilometers"
    )
):

    connection = get_db()

    rows = connection.execute(
        "SELECT * FROM addresses"
    ).fetchall()

    connection.close()

    results = []

    for row in rows:

        distance = calculate_distance(
            latitude,
            longitude,
            row["latitude"],
            row["longitude"]
        )

        if distance <= distance_km:

            address = row_to_address(row)

            address["distance_km"] = round(
                distance,
                2
            )

            results.append(address)

    # Closest addresses first
    results.sort(
        key=lambda address: address["distance_km"]
    )

    return {
        "search_location": {
            "latitude": latitude,
            "longitude": longitude
        },
        "distance_km": distance_km,
        "count": len(results),
        "addresses": results
    }
