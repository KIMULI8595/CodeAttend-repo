from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from attendance.utils.geofence import (
    calculate_distance,
    is_within_geofence,
    validate_location_accuracy,
)


class CalculateDistanceTests(SimpleTestCase):
    def test_identical_coordinates_have_zero_distance(self):
        distance = calculate_distance(
            latitude_one=Decimal("0.347596"),
            longitude_one=Decimal("32.582520"),
            latitude_two=Decimal("0.347596"),
            longitude_two=Decimal("32.582520"),
        )

        self.assertAlmostEqual(
            distance,
            0,
            places=5,
        )

    def test_calculates_distance_between_nearby_coordinates(self):
        distance = calculate_distance(
            latitude_one=0.347596,
            longitude_one=32.582520,
            latitude_two=0.348496,
            longitude_two=32.582520,
        )

        self.assertGreater(
            distance,
            90,
        )

        self.assertLess(
            distance,
            110,
        )

    def test_rejects_invalid_latitude(self):
        with self.assertRaises(ValidationError):
            calculate_distance(
                latitude_one=91,
                longitude_one=32.582520,
                latitude_two=0.347596,
                longitude_two=32.582520,
            )

    def test_rejects_invalid_longitude(self):
        with self.assertRaises(ValidationError):
            calculate_distance(
                latitude_one=0.347596,
                longitude_one=181,
                latitude_two=0.347596,
                longitude_two=32.582520,
            )

    def test_rejects_missing_coordinates(self):
        with self.assertRaises(ValidationError):
            calculate_distance(
                latitude_one=None,
                longitude_one=32.582520,
                latitude_two=0.347596,
                longitude_two=32.582520,
            )


class GeofenceTests(SimpleTestCase):
    def test_accepts_coordinates_inside_geofence(self):
        inside_geofence, distance = is_within_geofence(
            user_latitude=0.347596,
            user_longitude=32.582520,
            location_latitude=0.347596,
            location_longitude=32.582520,
            radius_metres=100,
        )

        self.assertTrue(
            inside_geofence,
        )

        self.assertAlmostEqual(
            distance,
            0,
            places=5,
        )

    def test_rejects_coordinates_outside_geofence(self):
        inside_geofence, distance = is_within_geofence(
            user_latitude=0.350596,
            user_longitude=32.582520,
            location_latitude=0.347596,
            location_longitude=32.582520,
            radius_metres=100,
        )

        self.assertFalse(
            inside_geofence,
        )

        self.assertGreater(
            distance,
            100,
        )

    def test_accepts_coordinate_on_geofence_boundary(self):
        inside_geofence, distance = is_within_geofence(
            user_latitude=0.347596,
            user_longitude=32.582520,
            location_latitude=0.347596,
            location_longitude=32.582520,
            radius_metres=0.01,
        )

        self.assertTrue(
            inside_geofence,
        )

        self.assertLessEqual(
            distance,
            0.01,
        )

    def test_rejects_zero_radius(self):
        with self.assertRaises(ValidationError):
            is_within_geofence(
                user_latitude=0.347596,
                user_longitude=32.582520,
                location_latitude=0.347596,
                location_longitude=32.582520,
                radius_metres=0,
            )


class LocationAccuracyTests(SimpleTestCase):
    def test_accepts_accurate_location(self):
        accuracy = validate_location_accuracy(
            accuracy_metres=20,
            maximum_accuracy_metres=50,
        )

        self.assertEqual(
            accuracy,
            20,
        )

    def test_accepts_accuracy_at_configured_limit(self):
        accuracy = validate_location_accuracy(
            accuracy_metres=50,
            maximum_accuracy_metres=50,
        )

        self.assertEqual(
            accuracy,
            50,
        )

    def test_rejects_inaccurate_location(self):
        with self.assertRaises(ValidationError):
            validate_location_accuracy(
                accuracy_metres=75,
                maximum_accuracy_metres=50,
            )

    def test_rejects_zero_accuracy(self):
        with self.assertRaises(ValidationError):
            validate_location_accuracy(
                accuracy_metres=0,
                maximum_accuracy_metres=50,
            )

    def test_rejects_missing_accuracy(self):
        with self.assertRaises(ValidationError):
            validate_location_accuracy(
                accuracy_metres=None,
                maximum_accuracy_metres=50,
            )