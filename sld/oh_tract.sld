<?xml version="1.0" encoding="ISO-8859-1"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc"
  xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:gml="http://www.opengis.net/gml"
  xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.0.0/StyledLayerDescriptor.xsd">
    <NamedLayer>
        <Name>Ohio population</Name>
        <UserStyle>
            <Name>Ohio population</Name>
            <Title>Population in Ohio</Title>
            <Abstract>Population Chloropleth</Abstract>
            <FeatureTypeStyle>
                <Rule>
                    <Title>0 - 1955</Title>
                    <ogc:Filter>
                        <ogc:PropertyIsBetween>
                            <ogc:PropertyName>POPTOT</ogc:PropertyName>
                            <ogc:LowerBoundary>
                                <ogc:Literal>0</ogc:Literal>
                            </ogc:LowerBoundary>
                            <ogc:UpperBoundary>
                                <ogc:Literal>1955</ogc:Literal>
                            </ogc:UpperBoundary>
                        </ogc:PropertyIsBetween>
                    </ogc:Filter>
                    <PolygonSymbolizer>
                        <Fill>
                            <!-- CssParameters allowed are fill (the color) and fill-opacity -->
                            <CssParameter name="fill">#FFFFFF</CssParameter>
                            <CssParameter name="fill-opacity">1.0</CssParameter>
                        </Fill>
                    </PolygonSymbolizer>
                </Rule>
                <Rule>
                    <Title>1955 - 3391</Title>
                    <ogc:Filter>
                        <ogc:PropertyIsBetween>
                            <ogc:PropertyName>POPTOT</ogc:PropertyName>
                            <ogc:LowerBoundary>
                                <ogc:Literal>1955</ogc:Literal>
                            </ogc:LowerBoundary>
                            <ogc:UpperBoundary>
                                <ogc:Literal>3391</ogc:Literal>
                            </ogc:UpperBoundary>
                        </ogc:PropertyIsBetween>
                    </ogc:Filter>
                    <PolygonSymbolizer>
                        <Fill>
                            <!-- CssParameters allowed are fill (the color) and fill-opacity -->
                            <CssParameter name="fill">#EEEEEE</CssParameter>
                            <CssParameter name="fill-opacity">1.0</CssParameter>
                        </Fill>
                    </PolygonSymbolizer>
                </Rule>
                <Rule>
                    <Title>3391 - 4849</Title>
                    <!-- like a linesymbolizer but with a fill too -->
                    <ogc:Filter>
                        <ogc:PropertyIsBetween>
                            <ogc:PropertyName>POPTOT</ogc:PropertyName>
                            <ogc:LowerBoundary>
                                <ogc:Literal>3391</ogc:Literal>
                            </ogc:LowerBoundary>
                            <ogc:UpperBoundary>
                                <ogc:Literal>4849</ogc:Literal>
                            </ogc:UpperBoundary>
                        </ogc:PropertyIsBetween>
                    </ogc:Filter>
                    <PolygonSymbolizer>
                        <Fill>
                            <!-- CssParameters allowed are fill (the color) and fill-opacity -->
                            <CssParameter name="fill">#DDDDDD</CssParameter>
                            <CssParameter name="fill-opacity">1.0</CssParameter>
                        </Fill>
                    </PolygonSymbolizer>
                </Rule>
                <Rule>
                    <Title>4849 - 6802</Title>
                    <!-- like a linesymbolizer but with a fill too -->
                    <ogc:Filter>
                        <ogc:PropertyIsBetween>
                            <ogc:PropertyName>POPTOT</ogc:PropertyName>
                            <ogc:LowerBoundary>
                                <ogc:Literal>4849</ogc:Literal>
                            </ogc:LowerBoundary>
                            <ogc:UpperBoundary>
                                <ogc:Literal>6802</ogc:Literal>
                            </ogc:UpperBoundary>
                        </ogc:PropertyIsBetween>
                    </ogc:Filter>
                    <PolygonSymbolizer>
                        <Fill>
                            <!-- CssParameters allowed are fill (the color) and fill-opacity -->
                            <CssParameter name="fill">#CCCCCC</CssParameter>
                            <CssParameter name="fill-opacity">1.0</CssParameter>
                        </Fill>
                    </PolygonSymbolizer>
                </Rule>
                <Rule>
                    <Title>6802 - 13421</Title>
                    <!-- like a linesymbolizer but with a fill too -->
                    <ogc:Filter>
                        <ogc:PropertyIsBetween>
                            <ogc:PropertyName>POPTOT</ogc:PropertyName>
                            <ogc:LowerBoundary>
                                <ogc:Literal>6802</ogc:Literal>
                            </ogc:LowerBoundary>
                            <ogc:UpperBoundary>
                                <ogc:Literal>13421</ogc:Literal>
                            </ogc:UpperBoundary>
                        </ogc:PropertyIsBetween>
                    </ogc:Filter>
                    <PolygonSymbolizer>
                        <Fill>
                            <!-- CssParameters allowed are fill (the color) and fill-opacity -->
                            <CssParameter name="fill">#BBBBBB</CssParameter>
                            <CssParameter name="fill-opacity">1.0</CssParameter>
                        </Fill>
                    </PolygonSymbolizer>
                </Rule>
                <Rule>
                    <Title>Boundary</Title>
                    <LineSymbolizer>
                        <Stroke>
                            <CssParameter name="stroke-width">0.5</CssParameter>
                            <CssParameter name="stroke">#000000</CssParameter>
                        </Stroke>
                    </LineSymbolizer>
                    <TextSymbolizer>
                        <Label>
                            <ogc:PropertyName>TRACT</ogc:PropertyName>
                        </Label>
                        <Font>
                            <CssParameter name="font-family">Times New Roman</CssParameter>
                            <CssParameter name="font-style">Normal</CssParameter>
                            <CssParameter name="font-size">10</CssParameter>
                        </Font>
                        <LabelPlacement>
                            <PointPlacement>
                                <AnchorPoint>
                                    <AnchorPointX>0.5</AnchorPointX>
                                    <AnchorPointY>0.5</AnchorPointY>
                                </AnchorPoint>
                            </PointPlacement>
                        </LabelPlacement>
                    </TextSymbolizer>
                </Rule>
            </FeatureTypeStyle>
        </UserStyle>
    </NamedLayer>
</StyledLayerDescriptor>
