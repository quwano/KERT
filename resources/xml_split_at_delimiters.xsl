<?xml version="1.0" encoding="UTF-8"?>
<!--
    XML前処理用XSLT 3.0: 句読点単位でテキストを分割

    処理内容:
    - p, title1-title5 直下のテキストノード → 句読点で区切り <seg> 要素でラップ
    - u, g, sub, sup → 句読点で要素自体を分割（複製）
    - ruby, yomikae → 原子的要素のため分割しない（identity）
-->
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    exclude-result-prefixes="xs">

    <xsl:output method="xml" encoding="UTF-8" indent="no"/>

    <!-- 句読点パターン（外部パラメータ） -->
    <xsl:param name="delimiter-pattern" as="xs:string" select="'[。、．，.,!！?？]'"/>

    <!-- デフォルト: identity transform -->
    <xsl:template match="@* | node()">
        <xsl:copy>
            <xsl:apply-templates select="@* | node()"/>
        </xsl:copy>
    </xsl:template>

    <!-- p, title1-title5: テキスト子ノードを句読点で分割し <seg> でラップ -->
    <xsl:template match="p | title1 | title2 | title3 | title4 | title5">
        <xsl:copy>
            <xsl:copy-of select="@*"/>
            <!-- Step 1: テキストノードに seg-marker を挿入、要素子は再帰処理 -->
            <xsl:variable name="marked_content">
                <xsl:for-each select="child::node()">
                    <xsl:choose>
                        <xsl:when test="self::text()">
                            <xsl:analyze-string select="." regex="{$delimiter-pattern}">
                                <xsl:matching-substring>
                                    <xsl:value-of select="."/>
                                    <seg-marker/>
                                </xsl:matching-substring>
                                <xsl:non-matching-substring>
                                    <xsl:value-of select="."/>
                                </xsl:non-matching-substring>
                            </xsl:analyze-string>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:apply-templates select="."/>
                        </xsl:otherwise>
                    </xsl:choose>
                </xsl:for-each>
            </xsl:variable>
            <!-- Step 2: seg-marker 終了単位でグループ化し <seg> でラップ -->
            <xsl:for-each-group select="$marked_content/node()" group-ending-with="seg-marker">
                <seg>
                    <xsl:copy-of select="current-group()[not(self::seg-marker)]"/>
                </seg>
            </xsl:for-each-group>
        </xsl:copy>
    </xsl:template>

    <!-- u, g, sub, sup: 句読点で要素自体を分割 -->
    <xsl:template match="u | g | sub | sup">
        <xsl:variable name="elName" select="name()"/>
        <xsl:variable name="elAttrs" select="@*"/>
        <!-- 子ノードを先に再帰処理（document fragmentとして格納） -->
        <xsl:variable name="processed_children">
            <xsl:apply-templates select="child::node()"/>
        </xsl:variable>
        <!-- テキストノードに split-marker を挿入 -->
        <xsl:variable name="marked_content">
            <xsl:for-each select="$processed_children/node()">
                <xsl:choose>
                    <xsl:when test="self::text()">
                        <xsl:analyze-string select="." regex="{$delimiter-pattern}">
                            <xsl:matching-substring>
                                <xsl:value-of select="."/>
                                <split-marker/>
                            </xsl:matching-substring>
                            <xsl:non-matching-substring>
                                <xsl:value-of select="."/>
                            </xsl:non-matching-substring>
                        </xsl:analyze-string>
                    </xsl:when>
                    <xsl:otherwise>
                        <xsl:copy-of select="."/>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:for-each>
        </xsl:variable>
        <!-- split-marker 終了単位で要素を複製分割 -->
        <!-- 分割された各要素の後に seg-marker を挿入（最後を除く） -->
        <xsl:variable name="groups" as="element()*">
            <xsl:for-each-group select="$marked_content/node()" group-ending-with="split-marker">
                <xsl:element name="{$elName}">
                    <xsl:copy-of select="$elAttrs"/>
                    <xsl:copy-of select="current-group()[not(self::split-marker)]"/>
                </xsl:element>
            </xsl:for-each-group>
        </xsl:variable>
        <xsl:for-each select="$groups">
            <xsl:copy-of select="."/>
            <xsl:if test="position() != last()">
                <seg-marker/>
            </xsl:if>
        </xsl:for-each>
    </xsl:template>

    <!-- ruby, yomikae: 分割しない（identity） -->
    <xsl:template match="ruby | yomikae">
        <xsl:copy>
            <xsl:apply-templates select="@* | node()"/>
        </xsl:copy>
    </xsl:template>

</xsl:stylesheet>
