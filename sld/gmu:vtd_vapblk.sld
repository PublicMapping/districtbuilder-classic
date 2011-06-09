<?xml version="1.0" encoding="ISO-8859-1"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>vapblk</Name>
    <UserStyle>
      <Title>Voting Age - Black Pop.</Title>
      <Abstract>A grayscale style showing the percentage of a given geounit&apos;s voting-age population that is black.</Abstract>
	<FeatureTypeStyle>
        <Rule>
          <Title>&gt; 60&#37; </Title>
          <ogc:Filter>
            <ogc:PropertyIsGreaterThanOrEqualTo>
              <ogc:PropertyName>percentage</ogc:PropertyName>
              <ogc:Literal>.60</ogc:Literal>
            </ogc:PropertyIsGreaterThanOrEqualTo>
          </ogc:Filter>
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#252525</CssParameter>
            </Fill>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Title>&gt; 30&#37; </Title>
          <ogc:Filter>
            <ogc:And>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>percentage</ogc:PropertyName>
                <ogc:Literal>.60</ogc:Literal>
              </ogc:PropertyIsLessThan>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>percentage</ogc:PropertyName>
                <ogc:Literal>.30</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>          
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#636363</CssParameter>
            </Fill>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Title>&gt; 15&#37;</Title>
          <ogc:Filter>
            <ogc:And>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>percentage</ogc:PropertyName>
                <ogc:Literal>.30</ogc:Literal>
              </ogc:PropertyIsLessThan>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>percentage</ogc:PropertyName>
                <ogc:Literal>.15</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>          
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#969696</CssParameter>
            </Fill>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Title>&gt; 05&#37;</Title>
          <ogc:Filter>
            <ogc:And>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>percentage</ogc:PropertyName>
                <ogc:Literal>.15</ogc:Literal>
              </ogc:PropertyIsLessThan>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>percentage</ogc:PropertyName>
                <ogc:Literal>.05</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>          
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#CCCCCC</CssParameter>
            </Fill>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Title>&lt; 05&#37;</Title>
          <ogc:Filter>
            <ogc:PropertyIsLessThan>
              <ogc:PropertyName>percentage</ogc:PropertyName>
              <ogc:Literal>.05</ogc:Literal>
            </ogc:PropertyIsLessThan>
          </ogc:Filter>          
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#F7F7F7</CssParameter>
            </Fill>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Title>Boundary</Title>
          <LineSymbolizer>
            <Stroke>
              <CssParameter name="stroke">#555555</CssParameter>
              <CssParameter name="stroke-width">0.25</CssParameter>
            </Stroke>
          </LineSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
