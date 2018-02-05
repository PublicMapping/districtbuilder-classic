from base import BaseTestCase

from tagging.models import Tag, TaggedItem

from redistricting.models import District


class TaggingTestCase(BaseTestCase):
    fixtures = ['redistricting_testdata.json']

    def test_tagging1(self):
        # Set all tags at once
        self.district1.tags = 'type=Neighborhood'
        alltags = Tag.objects.all().count()
        self.assertEqual(1, alltags, 'Total number of tags is incorrect.')

        # Change all the tags
        self.district1.tags = "type='hood"
        alltags = Tag.objects.all().count()
        self.assertEqual(2, alltags, 'Total number of tags is incorrect.')

        # Even though there are two tags, only one is used by this model
        tags = Tag.objects.usage_for_model(type(self.district1))
        self.assertEqual(1, len(tags),
                         'Total number of used tags is incorrect.')

        # Append a tag to a model
        Tag.objects.add_tag(self.district1, 'type=Neighborhood')
        alltags = Tag.objects.all().count()
        self.assertEqual(2, alltags, 'Total number of tags is incorrect.')

        # Now the model is using both tags
        tags = Tag.objects.usage_for_model(type(self.district1))
        self.assertEqual(2, len(tags),
                         'Total number of used tags is incorrect.')

    def test_tagging2(self):
        # Add tags to property, which parses them out
        self.district1.tags = 'type=typeval name=nameval extra=extraval'
        alltags = Tag.objects.all().count()
        self.assertEqual(3, alltags, 'Total number of tags is incorrect.')

        # Three different tags parsed and assigned to the model
        tags = Tag.objects.usage_for_model(type(self.district1))
        self.assertEqual(3, len(tags),
                         'Total number of used tags is incorrect.')

        # Filter the types of tags off the object
        tset = Tag.objects.get_for_object(self.district1)
        types = tset.filter(name__startswith='type')
        names = tset.filter(name__startswith='name')
        extras = tset.filter(name__startswith='extra')

        # This object has one type of tag for each key
        self.assertEqual(1, types.count())
        self.assertEqual(1, names.count())
        self.assertEqual(1, extras.count())

    def test_tagging3(self):
        # Add tags separately
        Tag.objects.add_tag(self.district1, 'type=typeval')
        Tag.objects.add_tag(self.district1, 'name=nameval')
        Tag.objects.add_tag(self.district1, 'extra=extraval')

        # Three different tags parsed and assigned to the model
        alltags = Tag.objects.get_for_object(self.district1).count()
        self.assertEqual(3, alltags)

        # Filter the types of tags off the object
        tset = Tag.objects.get_for_object(self.district1)
        types = tset.filter(name__startswith='type')
        names = tset.filter(name__startswith='name')
        extras = tset.filter(name__startswith='extra')

        # This object has one type of tag for each key
        self.assertEqual(1, types.count())
        self.assertEqual(1, names.count())
        self.assertEqual(1, extras.count())

    def test_tagging4(self):
        self.district1.tags = 'type=t1 name=n1 extra=e1'
        self.district2.tags = 'type=t2 name=n2 extra=e2'

        # Get the tags of a specific type
        tags = Tag.objects.filter(name__startswith='type=')
        # Get the union, where any model in the District Qset matches
        # any tag in the list of tags
        intersection = TaggedItem.objects.get_union_by_model(
            District.objects.all(), tags)

        self.assertEqual(2, intersection.count(),
                         'Number of models with type= tags are not correct.')
