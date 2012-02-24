<?xml version="1.0" encoding="ISO-8859-1"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>poptot</Name>
    <UserStyle>
      <Title>Population</Title>
      <Abstract>Community map styles communities.</Abstract>
      <FeatureTypeStyle>
        <Rule>
          <Title>Community</Title>
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#FFFFFF</CssParameter>
              <CssParameter name="fill-opacity">.01</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">#fdb913</CssParameter>
              <CssParameter name="stroke-width">6</CssParameter>
              <CssParameter name="stroke-opacity">1</CssParameter>
            </Stroke>
          </PolygonSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
