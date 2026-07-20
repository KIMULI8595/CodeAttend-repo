from math import asin, cos, radians, sin, sqrt

from django.core.exceptions import ValidationError


EARTH_RADIUS_METRES = 6_371_000


def _to_float(value, field_name):
    """
    Convert a coordinate or measurement to a float.

    Decimal values from Django model fields are supported.
    """
    if value is None:
        raise ValidationError(
            {
                field_name: (
                    f"{field_name.replace('_', ' ').capitalize()} "
                    "is required."
                ),
            },
        )

    try:
        return float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(
            {
                field_name: (
                    f"{field_name.replace('_', ' ').capitalize()} "
                    "must be a valid number."
                ),
            },
        ) from exc


def _validate_latitude(latitude, field_name):
    latitude = _to_float(
        latitude,
        field_name,
    )

    if not -90 <= latitude <= 90:
        raise ValidationError(
            {
                field_name: (
                    "Latitude must be between -90 and 90 degrees."
                ),
            },
        )

    return latitude


def _validate_longitude(longitude, field_name):
    longitude = _to_float(
        longitude,
        field_name,
    )

    if not -180 <= longitude <= 180:
        raise ValidationError(
            {
                field_name: (
                    "Longitude must be between -180 and 180 degrees."
                ),
            },
        )

    return longitude


def calculate_distance(
    latitude_one,
    longitude_one,
    latitude_two,
    longitude_two,
):
    """
    Calculate the distance in metres between two GPS coordinates.

    The Haversine formula is used so the result accounts for the
    curvature of the Earth.

    Args:
        latitude_one:
            Latitude of the first point in decimal degrees.
        longitude_one:
            Longitude of the first point in decimal degrees.
        latitude_two:
            Latitude of the second point in decimal degrees.
        longitude_two:
            Longitude of the second point in decimal degrees.

    Returns:
        float:
            Distance between the two points in metres.

    Raises:
        ValidationError:
            If any coordinate is missing, invalid, or outside its
            permitted range.
    """
    latitude_one = _validate_latitude(
        latitude_one,
        "latitude_one",
    )
    longitude_one = _validate_longitude(
        longitude_one,
        "longitude_one",
    )
    latitude_two = _validate_latitude(
        latitude_two,
        "latitude_two",
    )
    longitude_two = _validate_longitude(
        longitude_two,
        "longitude_two",
    )

    latitude_one_radians = radians(latitude_one)
    longitude_one_radians = radians(longitude_one)
    latitude_two_radians = radians(latitude_two)
    longitude_two_radians = radians(longitude_two)

    latitude_difference = (
        latitude_two_radians
        - latitude_one_radians
    )

    longitude_difference = (
        longitude_two_radians
        - longitude_one_radians
    )

    haversine_value = (
        sin(latitude_difference / 2) ** 2
        + cos(latitude_one_radians)
        * cos(latitude_two_radians)
        * sin(longitude_difference / 2) ** 2
    )

    angular_distance = 2 * asin(
        sqrt(
            min(
                1.0,
                haversine_value,
            ),
        ),
    )

    return EARTH_RADIUS_METRES * angular_distance


def is_within_geofence(
    user_latitude,
    user_longitude,
    location_latitude,
    location_longitude,
    radius_metres,
):
    """
    Determine whether a user's coordinates are inside a geofence.

    Args:
        user_latitude:
            User latitude in decimal degrees.
        user_longitude:
            User longitude in decimal degrees.
        location_latitude:
            Geofence centre latitude in decimal degrees.
        location_longitude:
            Geofence centre longitude in decimal degrees.
        radius_metres:
            Permitted radius in metres.

    Returns:
        tuple[bool, float]:
            A tuple containing:

            - whether the user is inside the geofence;
            - calculated distance from the geofence centre in metres.

    Raises:
        ValidationError:
            If coordinates or radius are invalid.
    """
    radius_metres = _to_float(
        radius_metres,
        "radius_metres",
    )

    if radius_metres <= 0:
        raise ValidationError(
            {
                "radius_metres": (
                    "Geofence radius must be greater than zero."
                ),
            },
        )

    distance_metres = calculate_distance(
        latitude_one=user_latitude,
        longitude_one=user_longitude,
        latitude_two=location_latitude,
        longitude_two=location_longitude,
    )

    return (
        distance_metres <= radius_metres,
        distance_metres,
    )


def validate_location_accuracy(
    accuracy_metres,
    maximum_accuracy_metres,
):
    """
    Validate the accuracy value supplied by the browser.

    Browser geolocation accuracy represents the estimated uncertainty
    radius in metres. A smaller value indicates a more precise reading.

    Args:
        accuracy_metres:
            Accuracy reported by the browser in metres.
        maximum_accuracy_metres:
            Largest acceptable uncertainty radius in metres.

    Returns:
        float:
            The validated accuracy value.

    Raises:
        ValidationError:
            If the reading is missing, invalid, non-positive, or less
            precise than the configured maximum.
    """
    accuracy_metres = _to_float(
        accuracy_metres,
        "accuracy_metres",
    )

    maximum_accuracy_metres = _to_float(
        maximum_accuracy_metres,
        "maximum_accuracy_metres",
    )

    if accuracy_metres <= 0:
        raise ValidationError(
            {
                "accuracy_metres": (
                    "GPS accuracy must be greater than zero."
                ),
            },
        )

    if maximum_accuracy_metres <= 0:
        raise ValidationError(
            {
                "maximum_accuracy_metres": (
                    "Maximum GPS accuracy must be greater than zero."
                ),
            },
        )

    if accuracy_metres > maximum_accuracy_metres:
        raise ValidationError(
            {
                "accuracy_metres": (
                    "The GPS reading is not accurate enough. "
                    f"Reported accuracy is approximately "
                    f"{accuracy_metres:.2f} metres, but the maximum "
                    f"allowed value is "
                    f"{maximum_accuracy_metres:.2f} metres. "
                    "Move to an open area and try again."
                ),
            },
        )

    return accuracy_metres