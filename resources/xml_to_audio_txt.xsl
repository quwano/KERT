<?xml version="1.0" encoding="UTF-8"?>
<!--
    XML to audio.txt (読み上げ用テキスト) 変換用XSLT 3.0

    変換ルール:
    - title1-title5: 読み仮名変換後のテキスト + 改行
    - p: 読み仮名変換後のテキスト + 改行
    - ruby: @yomi属性値（読み仮名）を出力
    - yomikae: @yomi属性値（読み替え）を出力
    - u, g, sub, sup: 要素内容のみ出力
-->
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:output method="text" encoding="UTF-8"/>

    <!-- ルート要素 -->
    <xsl:template match="root">
        <xsl:apply-templates select="title1 | title2 | title3 | title4 | title5 | p"/>
    </xsl:template>

    <!-- タイトル要素: 読み仮名テキスト + 改行 -->
    <xsl:template match="title1 | title2 | title3 | title4 | title5">
        <xsl:call-template name="process-inline-content"/>
        <xsl:text>&#10;</xsl:text>
    </xsl:template>

    <!-- 段落要素: 読み仮名テキスト + 改行 -->
    <xsl:template match="p">
        <xsl:call-template name="process-inline-content"/>
        <xsl:text>&#10;</xsl:text>
    </xsl:template>

    <!-- インライン要素の処理 -->
    <xsl:template name="process-inline-content">
        <xsl:for-each select="node()">
            <xsl:choose>
                <!-- ruby要素: @yomi属性値を出力 -->
                <xsl:when test="self::ruby">
                    <xsl:choose>
                        <xsl:when test="@yomi">
                            <xsl:value-of select="@yomi"/>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:value-of select="."/>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>

                <!-- yomikae要素: @yomi属性値を出力 -->
                <xsl:when test="self::yomikae">
                    <xsl:choose>
                        <xsl:when test="@yomi">
                            <xsl:value-of select="@yomi"/>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:value-of select="."/>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:when>

                <!-- 装飾要素: 再帰的に処理 -->
                <xsl:when test="self::u or self::g or self::sub or self::sup">
                    <xsl:for-each select="node()">
                        <xsl:call-template name="process-node"/>
                    </xsl:for-each>
                </xsl:when>

                <!-- テキストノード -->
                <xsl:when test="self::text()">
                    <xsl:variable name="text" select="replace(., '\s+', ' ')"/>
                    <xsl:if test="normalize-space($text) != ''">
                        <xsl:value-of select="$text"/>
                    </xsl:if>
                </xsl:when>
            </xsl:choose>
        </xsl:for-each>
    </xsl:template>

    <!-- 個別ノードの処理 -->
    <xsl:template name="process-node">
        <xsl:choose>
            <xsl:when test="self::ruby">
                <xsl:choose>
                    <xsl:when test="@yomi">
                        <xsl:value-of select="@yomi"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:value-of select="."/>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:when>

            <xsl:when test="self::yomikae">
                <xsl:choose>
                    <xsl:when test="@yomi">
                        <xsl:value-of select="@yomi"/>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:value-of select="."/>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:when>

            <xsl:when test="self::text()">
                <xsl:variable name="text" select="replace(., '\s+', ' ')"/>
                <xsl:if test="normalize-space($text) != ''">
                    <xsl:value-of select="$text"/>
                </xsl:if>
            </xsl:when>

            <xsl:otherwise>
                <!-- ネストした装飾要素 -->
                <xsl:for-each select="node()">
                    <xsl:call-template name="process-node"/>
                </xsl:for-each>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

</xsl:stylesheet>
