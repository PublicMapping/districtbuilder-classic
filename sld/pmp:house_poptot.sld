<?xml version="1.0" encoding="ISO-8859-1"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <Name>poptot</Name>
    <UserStyle>
      <Title>Population</Title>
      <Abstract>District styles for state house districts.</Abstract>
      <FeatureTypeStyle>
        <Rule>
          <Title>Far Over Target</Title>
          <ogc:Filter>
            <ogc:And>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>number</ogc:PropertyName>
                <ogc:Literal>88011</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>          
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#ebb95e</CssParameter>
              <CssParameter name="fill-opacity">.5</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">#fdb913</CssParameter>
              <CssParameter name="stroke-width">6</CssParameter>
              <CssParameter name="stroke-opacity">1</CssParameter>
            </Stroke>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Title>Over Target</Title>
          <ogc:Filter>
            <ogc:And>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>number</ogc:PropertyName>
                <ogc:Literal>88011</ogc:Literal>
              </ogc:PropertyIsLessThan>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>number</ogc:PropertyName>
                <ogc:Literal>84011</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>          
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#ead3a7</CssParameter>
              <CssParameter name="fill-opacity">.5</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">#fdb913</CssParameter>
              <CssParameter name="stroke-width">6</CssParameter>
              <CssParameter name="stroke-opacity">1</CssParameter>
            </Stroke>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Title>Meets Target</Title>
          <ogc:Filter>
            <ogc:PropertyIsLessThan>
              <ogc:PropertyName>number</ogc:PropertyName>
              <ogc:Literal>84011</ogc:Literal>
            </ogc:PropertyIsLessThan>
            <ogc:PropertyIsGreaterThanOrEqualTo>
              <ogc:PropertyName>number</ogc:PropertyName>
              <ogc:Literal>76010</ogc:Literal>
            </ogc:PropertyIsGreaterThanOrEqualTo>
          </ogc:Filter>
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#eeeeee</CssParameter>
              <CssParameter name="fill-opacity">.5</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">#fdb913</CssParameter>
              <CssParameter name="stroke-width">6</CssParameter>
              <CssParameter name="stroke-opacity">1</CssParameter>
            </Stroke>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Title>Under Target</Title>
          <ogc:Filter>
            <ogc:And>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>number</ogc:PropertyName>
                <ogc:Literal>76010</ogc:Literal>
              </ogc:PropertyIsLessThan>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>number</ogc:PropertyName>
                <ogc:Literal>72010</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>          
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#a2d5d0</CssParameter>
              <CssParameter name="fill-opacity">.5</CssParameter>
            </Fill>
            <Stroke>
              <CssParameter name="stroke">#fdb913</CssParameter>
              <CssParameter name="stroke-width">6</CssParameter>
              <CssParameter name="stroke-opacity">1</CssParameter>
            </Stroke>
          </PolygonSymbolizer>
        </Rule>
        <Rule>
          <Title>Far Under Target</Title>
          <ogc:Filter>
            <ogc:PropertyIsLessThan>
              <ogc:PropertyName>number</ogc:PropertyName>
              <ogc:Literal>72010</ogc:Literal>
            </ogc:PropertyIsLessThan>
          </ogc:Filter>          
          <PolygonSymbolizer>
            <Fill>
              <CssParameter name="fill">#0aac98</CssParameter>
              <CssParameter name="fill-opacity">.5</CssParameter>
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
