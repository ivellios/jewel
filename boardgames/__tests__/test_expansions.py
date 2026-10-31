"""Focused model tests for BGGExpansion expansion relationships."""

from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from django.test import TestCase

from boardgames.models import BGGExpansion, BGGMetadata

from .factories import BGGExpansionFactory, BGGMetadataFactory


class BGGExpansionModelTest(TestCase):
    """Verify BGGExpansion constraints and expansion behavior."""

    def test_basic_expansion_link(self):
        """An expansion links to exactly one base game."""
        base = BGGMetadata.objects.create(bgg_id=1, name="Base Game")
        expansion = BGGMetadata.objects.create(bgg_id=2, name="Expansion")

        link = BGGExpansion.objects.create(
            expansion=expansion,
            parent=base,
            exp_type="boardgameexpansion",
        )

        self.assertEqual(link.expansion.bgg_id, 2)
        self.assertEqual(link.parent.bgg_id, 1)
        self.assertEqual(link.exp_type, "boardgameexpansion")

    def test_self_link_rejected(self):
        """A game cannot be its own expansion base."""
        game = BGGMetadata.objects.create(bgg_id=42, name="Standalone")

        with self.assertRaises(IntegrityError):
            BGGExpansion.objects.create(
                expansion=game,
                parent=game,
            )

    def test_duplicate_link_rejected(self):
        """The same (expansion, parent) pair is unique."""
        base = BGGMetadata.objects.create(bgg_id=10, name="Base")
        expansion = BGGMetadata.objects.create(bgg_id=20, name="Expansion")

        BGGExpansion.objects.create(expansion=expansion, parent=base)

        with self.assertRaises(IntegrityError):
            BGGExpansion.objects.create(expansion=expansion, parent=base)

    def test_idempotent_upsert_via_get_or_create(self):
        """Repeated get_or_create is idempotent — one row survives."""
        base = BGGMetadata.objects.create(bgg_id=30, name="Base")
        expansion = BGGMetadata.objects.create(bgg_id=40, name="Expansion")

        link, created1 = BGGExpansion.objects.get_or_create(
            expansion=expansion,
            parent=base,
            defaults={"exp_type": "boardgameexpansion"},
        )
        self.assertTrue(created1)

        link2, created2 = BGGExpansion.objects.get_or_create(
            expansion=expansion,
            parent=base,
            defaults={"exp_type": "boardgameexpansion"},
        )
        self.assertFalse(created2)
        self.assertEqual(link.pk, link2.pk)

        # Exactly one row must exist.
        self.assertEqual(BGGExpansion.objects.count(), 1)

    def test_multiple_bases_for_one_expansion(self):
        """An expansion can link to multiple base games."""
        base1 = BGGMetadata.objects.create(bgg_id=100, name="Base A")
        base2 = BGGMetadata.objects.create(bgg_id=200, name="Base B")
        expansion = BGGMetadata.objects.create(
            bgg_id=300, name="Expansion Pack"
        )

        BGGExpansion.objects.create(
            expansion=expansion,
            parent=base1,
            order=1,
            exp_type="boardgameexpansion",
        )
        BGGExpansion.objects.create(
            expansion=expansion,
            parent=base2,
            order=2,
            exp_type="boardgameexpansion",
        )

        links = list(expansion.expansions_of.all())
        self.assertEqual(len(links), 2)
        self.assertEqual(
            sorted(links, key=lambda l: l.order),
            sorted(
                links,
                key=lambda l: l.order,
            ),
        )

    def test_order_field(self):
        """Order controls the sequence among multiple bases."""
        base1 = BGGMetadata.objects.create(bgg_id=400, name="Base 1")
        base2 = BGGMetadata.objects.create(bgg_id=500, name="Base 2")
        expansion = BGGMetadata.objects.create(
            bgg_id=600, name="Multi-Base Expansion"
        )

        BGGExpansion.objects.create(
            expansion=expansion, parent=base2, order=2
        )
        BGGExpansion.objects.create(
            expansion=expansion, parent=base1, order=1
        )

        links = list(expansion.expansions_of.order_by("order"))
        self.assertEqual(links[0].parent.bgg_id, 400)
        self.assertEqual(links[1].parent.bgg_id, 500)

    def test_default_order_is_zero(self):
        """Unset order defaults to 0."""
        base = BGGMetadata.objects.create(bgg_id=700, name="Single Base")
        expansion = BGGMetadata.objects.create(
            bgg_id=800, name="Single Expansion"
        )
        link = BGGExpansion.objects.create(
            expansion=expansion, parent=base
        )
        self.assertEqual(link.order, 0)

    def test_exp_type_stored(self):
        """The BGG expansion type is persisted."""
        base = BGGMetadata.objects.create(bgg_id=900, name="Base")
        expansion = BGGMetadata.objects.create(bgg_id=910, name="Expansion")
        link = BGGExpansion.objects.create(
            expansion=expansion, parent=base, exp_type="boardgamesubdirectory"
        )
        self.assertEqual(link.exp_type, "boardgamesubdirectory")

    def test_null_exp_type_allowed(self):
        """exp_type can be None for unknown types."""
        base = BGGMetadata.objects.create(bgg_id=920, name="Base")
        expansion = BGGMetadata.objects.create(
            bgg_id=930, name="Expansion"
        )
        link = BGGExpansion.objects.create(
            expansion=expansion,
            parent=base,
            exp_type=None,
        )
        self.assertIsNone(link.exp_type)

    def test_str_representation(self):
        """String uses both BGG IDs."""
        base = BGGMetadata.objects.create(bgg_id=1, name="Base")
        expansion = BGGMetadata.objects.create(bgg_id=2, name="Expansion")
        link = BGGExpansion.objects.create(
            expansion=expansion, parent=base
        )
        self.assertEqual(str(link), "BGG#2 -> BGG#1")

    def test_expansions_of_reverse_relation(self):
        """The reverse relation collects all bases for an expansion."""
        base1 = BGGMetadata.objects.create(bgg_id=1000, name="Base A")
        base2 = BGGMetadata.objects.create(bgg_id=1100, name="Base B")
        expansion = BGGMetadata.objects.create(
            bgg_id=1200, name="Expansion"
        )

        BGGExpansion.objects.create(
            expansion=expansion, parent=base1, order=1
        )
        BGGExpansion.objects.create(
            expansion=expansion, parent=base2, order=2
        )

        ids = list(expansion.expansions_of.values_list("parent__bgg_id"))
        self.assertEqual(set(id[0] for id in ids), {1000, 1100})

    def test_parent_reverse_relation(self):
        """The reverse relation lists expansions of a base game."""
        base = BGGMetadata.objects.create(bgg_id=2000, name="Base")
        exp_a = BGGMetadata.objects.create(bgg_id=2100, name="Expansion A")
        exp_b = BGGMetadata.objects.create(bgg_id=2200, name="Expansion B")

        BGGExpansion.objects.create(
            expansion=exp_a, parent=base
        )
        BGGExpansion.objects.create(
            expansion=exp_b, parent=base
        )

        ids = list(base.is_expanded_by.values_list("expansion__bgg_id"))
        self.assertEqual(set(id[0] for id in ids), {2100, 2200})

    def test_cascade_delete_expansion(self):
        """Deleting an expansion game removes its expansion links."""
        base = BGGMetadata.objects.create(bgg_id=3000, name="Base")
        expansion = BGGMetadata.objects.create(bgg_id=3100, name="Expansion")

        BGGExpansion.objects.create(
            expansion=expansion, parent=base
        )
        self.assertEqual(BGGExpansion.objects.count(), 1)

        expansion.delete()
        self.assertEqual(BGGExpansion.objects.count(), 0)

    def test_cascade_delete_parent(self):
        """Deleting a base game removes its expansion links."""
        base = BGGMetadata.objects.create(bgg_id=4000, name="Base")
        expansion = BGGMetadata.objects.create(bgg_id=4100, name="Expansion")

        BGGExpansion.objects.create(
            expansion=expansion, parent=base
        )
        self.assertEqual(BGGExpansion.objects.count(), 1)

        base.delete()
        self.assertEqual(BGGExpansion.objects.count(), 0)
