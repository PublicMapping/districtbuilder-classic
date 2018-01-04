"""Limited subset of azavea/django-sld's generator module

This module preserves that module's structure for extensibility,
but only borrows the as_quantiles method.
"""

import numpy as np

from django.contrib.gis.db.models import fields
from pysal.esda.mapclassify import Quantiles
from sld import (Filter, LineSymbolizer, PointSymbolizer, PolygonSymbolizer,
                 PropertyCriterion, StyledLayerDescriptor)


def as_quantiles(*args, **kwargs):
    """
    Generate Quantile classes from the provided queryset. If the queryset
    is empty, no class breaks are returned. For more information on the Quantile
    classifier, please visit:

    U{http://pysal.geodacenter.org/1.2/library/esda/mapclassify.html#pysal.esda.mapclassify.Quantiles}

    @type  queryset: QuerySet
    @param queryset: The query set that contains the entire distribution of
        data values.
    @type  field: string
    @param field: The name of the field on the model in the queryset that
        contains the data values.
    @type  nclasses: integer
    @param nclasses: The number of class breaks desired.
    @type  geofield: string
    @param geofield: The name of the geometry field. Defaults to 'geom'.
    @rtype: L{sld.StyledLayerDescriptor}
    @returns: An SLD object that represents the class breaks.
    """
    return _as_classification(Quantiles, *args, **kwargs)


def _as_classification(classification,
                       queryset,
                       field,
                       nclasses,
                       geofield='geom',
                       propertyname=None,
                       userstyletitle=None,
                       featuretypestylename=None,
                       colorbrewername='',
                       invertgradient=False,
                       **kwargs):
    """
    Accept a queryset of objects, and return the values of the class breaks
    on the data distribution. If the queryset is empty, no class breaks are
    computed.

    @type  classification: pysal classifier
    @param classification: A classification class defined in
        pysal.esda.mapclassify. As of version 1.0.1, this list is comprised of:

          - Equal_Interval
          - Fisher_Jenks
          - Jenks_Caspall
          - Jenks_Caspall_Forced
          - Jenks_Caspall_Sampled
          - Max_P_Classifier
          - Maximum_Breaks
          - Natural_Breaks
          - Quantiles

    @type  queryset: QuerySet
    @param queryset: The query set that contains the entire distribution of data values.
    @type     field: string
    @param    field: The name of the field on the model in the queryset that contains the data
        values.
    @type  nclasses: integer
    @param nclasses: The number of class breaks desired.
    @type  geofield: string
    @keyword geofield: The name of the geography column on the model. Defaults to 'geom'
    @type  propertyname: string
    @keyword propertyname: The name of the filter property name, if different from the model field.
    @type  userstyletitle: string
    @keyword userstyletitle: The title of the UserStyle element.
    @type  featuretypestylename: string
    @keyword featuretypestylename: The name of the FeatureTypeStyle element.
    @type    colorbrewername: string
    @keyword colorbrewername: The name of a colorbrewer ramp name. Must have the same # of
        corresponding classes as nclasses.
    @type    invertgradient: boolean
    @keyword invertgradient: Should the resulting SLD have colors from high to low, instead of low
        to high?
    @type    kwargs: keywords
    @param   kwargs: Additional keyword arguments for the classifier.
    @rtype: L{sld.StyledLayerDescriptor}
    @returns: An SLD class object that represents the classification scheme
        and filters.
    """
    thesld = StyledLayerDescriptor()

    ftype = queryset.model._meta.get_field(geofield)
    if isinstance(ftype, fields.LineStringField) or isinstance(
            ftype, fields.MultiLineStringField):
        symbolizer = LineSymbolizer
    elif isinstance(ftype, fields.PolygonField) or isinstance(
            ftype, fields.MultiPolygonField):
        symbolizer = PolygonSymbolizer
    else:
        # PointField, MultiPointField, GeometryField, or GeometryCollectionField
        symbolizer = PointSymbolizer

    if propertyname is None:
        propertyname = field

    nl = thesld.create_namedlayer('%d breaks on "%s" as %s' %
                                  (nclasses, field, classification.__name__))
    us = nl.create_userstyle()
    if userstyletitle is not None:
        us.Title = str(userstyletitle)
    fts = us.create_featuretypestyle()
    if featuretypestylename is not None:
        fts.Name = str(featuretypestylename)

    # with just one class, make a single static style with no filters
    if nclasses == 1:
        rule = fts.create_rule(propertyname, symbolizer=symbolizer)
        shade = 0 if invertgradient else 255
        shade = '#%02x%02x%02x' % (
            shade,
            shade,
            shade,
        )

        # no filters for one class
        if symbolizer == PointSymbolizer:
            rule.PointSymbolizer.Graphic.Mark.Fill.CssParameters[
                0].Value = shade
        elif symbolizer == LineSymbolizer:
            rule.LineSymbolizer.Stroke.CssParameters[0].Value = shade
        elif symbolizer == PolygonSymbolizer:
            rule.PolygonSymbolizer.Stroke.CssParameters[0].Value = '#000000'
            rule.PolygonSymbolizer.Fill.CssParameters[0].Value = shade

        thesld.normalize()

        return thesld

    # with more than one class, perform classification
    datavalues = np.array(
        queryset.order_by(field).values_list(field, flat=True))
    q = classification(datavalues, nclasses, **kwargs)

    shades = None
    if q.k == nclasses and colorbrewername and not colorbrewername == '':
        try:
            import colorbrewer
            shades = getattr(colorbrewer, colorbrewername)[nclasses]

            if invertgradient:
                shades.reverse()
        except (ImportError, KeyError):
            # could not import colorbrewer, or nclasses unavailable
            pass

    for i, qbin in enumerate(q.bins):
        if type(qbin) == np.ndarray:
            qbin = qbin[0]

        title = '<= %s' % qbin
        rule = fts.create_rule(title, symbolizer=symbolizer)

        if shades:
            shade = '#%02x%02x%02x' % shades[i]
        else:
            shade = (float(q.k - i) / q.k) * 255
            if invertgradient:
                shade = 255 - shade
            shade = '#%02x%02x%02x' % (
                shade,
                shade,
                shade,
            )

        if symbolizer == PointSymbolizer:
            rule.PointSymbolizer.Graphic.Mark.Fill.CssParameters[
                0].Value = shade
        elif symbolizer == LineSymbolizer:
            rule.LineSymbolizer.Stroke.CssParameters[0].Value = shade
        elif symbolizer == PolygonSymbolizer:
            rule.PolygonSymbolizer.Stroke.CssParameters[0].Value = '#000000'
            rule.PolygonSymbolizer.Fill.CssParameters[0].Value = shade

        # now add the filters
        if i > 0:
            f_low = Filter(rule)
            f_low.PropertyIsGreaterThan = PropertyCriterion(
                f_low, 'PropertyIsGreaterThan')
            f_low.PropertyIsGreaterThan.PropertyName = propertyname
            f_low.PropertyIsGreaterThan.Literal = str(q.bins[i - 1])

        f_high = Filter(rule)
        f_high.PropertyIsLessThanOrEqualTo = PropertyCriterion(
            f_high, 'PropertyIsLessThanOrEqualTo')
        f_high.PropertyIsLessThanOrEqualTo.PropertyName = propertyname
        f_high.PropertyIsLessThanOrEqualTo.Literal = str(qbin)

        if i > 0:
            rule.Filter = f_low + f_high
        else:
            rule.Filter = f_high

    thesld.normalize()

    return thesld
