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
                    <Title>Boundary</Title>
                    <LineSymbolizer>
                        <Stroke>
                            <CssParameter name="stroke-width">1.0</CssParameter>
                            <CssParameter name="stroke">#FFA600</CssParameter>
                        </Stroke>
                    </LineSymbolizer>
                    <TextSymbolizer>
                        <Label>
                            <ogc:PropertyName>NAME00</ogc:PropertyName>
                        </Label>
                        <Font>
                            <CssParameter name="font-family">Times New Roman</CssParameter>
                            <CssParameter name="font-style">Normal</CssParameter>
                            <CssParameter name="font-size">14</CssParameter>
                        </Font>
                        <LabelPlacement>
                            <PointPlacement>
                                <AnchorPoint>
                                    <AnchorPointX>0.5</AnchorPointX>
                                    <AnchorPointY>0.5</AnchorPointY>
                                </AnchorPoint>
                            </PointPlacement>
                        </LabelPlacement>
                        <Halo>
                            <Radius>
                                <ogc:Literal>2</ogc:Literal>
                            </Radius>
                            <Fill>
                                <CssParameter name="fill">#FFFFFF</CssParameter>
                                <CssParameter name="fill-opacity">1.0</CssParameter>
                            </Fill>
                        </Halo>
                    </TextSymbolizer>
                </Rule>
            </FeatureTypeStyle>
        </UserStyle>
    </NamedLayer>
</StyledLayerDescriptor>
