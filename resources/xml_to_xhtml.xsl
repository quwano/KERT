<?xml version="1.0" encoding="UTF-8"?>
<!--
    XML to XHTML本文変換用XSLT 3.0

    変換ルール:
    - 各読み上げ単位（ruby, yomikae, テキストノード）をspan要素でラップ
    - span要素にはdata-indexで順序番号を付与（Pythonでidに変換）
    - title1-title5: タイトルテキスト（XHTML装飾付き）、セクション単位で出力
    - p: 段落テキスト（XHTML装飾付き）
    - ruby: <ruby><rb>親字</rb><rt>読み</rt></ruby>
    - yomikae: 要素内容のみ出力（表示用テキスト）
    - u: <u>下線</u>
    - g: <strong>強調</strong>
    - sub: <sub>下付き</sub>
    - sup: <sup>上付き</sup>
-->
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

    <xsl:output method="xml" encoding="UTF-8" omit-xml-declaration="yes"/>

    <!-- アキュムレータでグローバルカウンタを管理 -->
    <xsl:accumulator name="span-counter" as="xs:integer" initial-value="0"
        xmlns:xs="http://www.w3.org/2001/XMLSchema">
        <xsl:accumulator-rule match="ruby | yomikae | seg | text()[normalize-space() and not(ancestor::ruby) and not(ancestor::yomikae) and not(ancestor::seg)]"
            select="$value + 1"/>
    </xsl:accumulator>

    <xsl:mode use-accumulators="span-counter"/>

    <!-- ルート要素: セクション単位で出力 -->
    <xsl:template match="root">
        <result>
            <xsl:for-each-group select="*" group-starting-with="title1 | title2 | title3 | title4 | title5">
                <section level="{if (current-group()[1][self::title1]) then '1'
                                else if (current-group()[1][self::title2]) then '2'
                                else if (current-group()[1][self::title3]) then '3'
                                else if (current-group()[1][self::title4]) then '4'
                                else if (current-group()[1][self::title5]) then '5'
                                else '0'}">
                    <xsl:for-each select="current-group()">
                        <xsl:choose>
                            <xsl:when test="self::title1 | self::title2 | self::title3 | self::title4 | self::title5">
                                <heading>
                                    <xsl:apply-templates mode="with-span"/>
                                </heading>
                                <heading-text>
                                    <xsl:apply-templates mode="no-span"/>
                                </heading-text>
                            </xsl:when>
                            <xsl:when test="self::p">
                                <p><xsl:apply-templates mode="with-span"/></p>
                            </xsl:when>
                        </xsl:choose>
                    </xsl:for-each>
                </section>
            </xsl:for-each-group>
        </result>
    </xsl:template>

    <!-- ruby要素: spanでラップしてXHTMLのruby/rb/rtに変換 -->
    <xsl:template match="ruby" mode="with-span">
        <span data-index="{accumulator-before('span-counter')}">
            <ruby>
                <rb><xsl:apply-templates mode="no-span"/></rb>
                <rt><xsl:value-of select="@yomi"/></rt>
            </ruby>
        </span>
    </xsl:template>

    <!-- yomikae要素: spanでラップして表示用テキストを出力（data-yomiに読みを保持） -->
    <xsl:template match="yomikae" mode="with-span">
        <span data-index="{accumulator-before('span-counter')}" data-yomi="{@yomi}">
            <xsl:apply-templates mode="no-span"/>
        </span>
    </xsl:template>

    <!-- seg要素: spanでラップして内容を出力（yomikae読み情報を保持） -->
    <xsl:template match="seg" mode="with-span">
        <span data-index="{accumulator-before('span-counter')}">
            <xsl:apply-templates mode="seg-content"/>
        </span>
    </xsl:template>

    <!-- u要素: XHTMLのuタグに変換（内部は再帰処理） -->
    <xsl:template match="u" mode="with-span">
        <u><xsl:apply-templates mode="with-span"/></u>
    </xsl:template>

    <!-- g要素: XHTMLのstrongタグに変換 -->
    <xsl:template match="g" mode="with-span">
        <strong><xsl:apply-templates mode="with-span"/></strong>
    </xsl:template>

    <!-- sub要素: XHTMLのsubタグに変換 -->
    <xsl:template match="sub" mode="with-span">
        <sub><xsl:apply-templates mode="with-span"/></sub>
    </xsl:template>

    <!-- sup要素: XHTMLのsupタグに変換 -->
    <xsl:template match="sup" mode="with-span">
        <sup><xsl:apply-templates mode="with-span"/></sup>
    </xsl:template>

    <!-- テキストノード: spanでラップ -->
    <xsl:template match="text()[normalize-space()]" mode="with-span">
        <xsl:choose>
            <!-- ruby/yomikae内のテキストはそのまま -->
            <xsl:when test="ancestor::ruby or ancestor::yomikae or ancestor::seg">
                <xsl:value-of select="."/>
            </xsl:when>
            <xsl:otherwise>
                <span data-index="{accumulator-before('span-counter')}">
                    <xsl:value-of select="."/>
                </span>
            </xsl:otherwise>
        </xsl:choose>
    </xsl:template>

    <!-- 空白のみのテキストノード: インライン要素間の空白は保持 -->
    <xsl:template match="text()[not(normalize-space())]" mode="with-span">
        <xsl:if test="parent::u or parent::g or parent::sub or parent::sup or parent::title1 or parent::title2 or parent::title3 or parent::title4 or parent::title5 or parent::p">
            <xsl:if test="preceding-sibling::node() and following-sibling::node()">
                <xsl:value-of select="' '"/>
            </xsl:if>
        </xsl:if>
    </xsl:template>

    <!-- no-spanモード: spanを付けずに変換 -->
    <xsl:template match="ruby" mode="no-span">
        <ruby>
            <rb><xsl:apply-templates mode="no-span"/></rb>
            <rt><xsl:value-of select="@yomi"/></rt>
        </ruby>
    </xsl:template>

    <xsl:template match="yomikae" mode="no-span">
        <xsl:apply-templates mode="no-span"/>
    </xsl:template>

    <xsl:template match="seg" mode="no-span">
        <xsl:apply-templates mode="no-span"/>
    </xsl:template>

    <xsl:template match="u" mode="no-span">
        <u><xsl:apply-templates mode="no-span"/></u>
    </xsl:template>

    <xsl:template match="g" mode="no-span">
        <strong><xsl:apply-templates mode="no-span"/></strong>
    </xsl:template>

    <xsl:template match="sub" mode="no-span">
        <sub><xsl:apply-templates mode="no-span"/></sub>
    </xsl:template>

    <xsl:template match="sup" mode="no-span">
        <sup><xsl:apply-templates mode="no-span"/></sup>
    </xsl:template>

    <xsl:template match="text()" mode="no-span">
        <xsl:value-of select="."/>
    </xsl:template>

    <!-- seg-contentモード: seg内部用（yomikae読み情報を保持） -->
    <xsl:template match="ruby" mode="seg-content">
        <ruby>
            <rb><xsl:apply-templates mode="no-span"/></rb>
            <rt><xsl:value-of select="@yomi"/></rt>
        </ruby>
    </xsl:template>

    <xsl:template match="yomikae" mode="seg-content">
        <span data-yomi="{@yomi}"><xsl:apply-templates mode="no-span"/></span>
    </xsl:template>

    <xsl:template match="u" mode="seg-content">
        <u><xsl:apply-templates mode="seg-content"/></u>
    </xsl:template>

    <xsl:template match="g" mode="seg-content">
        <strong><xsl:apply-templates mode="seg-content"/></strong>
    </xsl:template>

    <xsl:template match="sub" mode="seg-content">
        <sub><xsl:apply-templates mode="seg-content"/></sub>
    </xsl:template>

    <xsl:template match="sup" mode="seg-content">
        <sup><xsl:apply-templates mode="seg-content"/></sup>
    </xsl:template>

    <xsl:template match="text()" mode="seg-content">
        <xsl:value-of select="."/>
    </xsl:template>

</xsl:stylesheet>
