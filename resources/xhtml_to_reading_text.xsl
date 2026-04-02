<?xml version="1.0" encoding="UTF-8"?>
<!--
    XHTML fragment to reading text conversion XSLT 3.0

    Input:  <fragment>...XHTML fragment...</fragment>
    Output: plain reading text

    Rules:
    - ruby:             output rt child text (reading)
    - span[@data-yomi]: output @data-yomi value
    - img:              output @alt if non-empty
    - math:             output nothing (caller pre-processes to span[@data-yomi])
    - u, strong, sub, sup, em, plain span: recurse into children (default template)
    - text nodes:       output as-is
-->
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:output method="text" encoding="UTF-8"/>

  <!-- ルート: 子を処理 -->
  <xsl:template match="fragment">
    <xsl:apply-templates/>
  </xsl:template>

  <!-- ruby: rt（読み仮名）のみ出力 -->
  <xsl:template match="ruby">
    <xsl:value-of select="rt"/>
  </xsl:template>

  <!-- data-yomi付きspan: yomi値を出力 -->
  <xsl:template match="span[@data-yomi]">
    <xsl:value-of select="@data-yomi"/>
  </xsl:template>

  <!-- img: alt属性値を出力（空でなければ） -->
  <xsl:template match="img">
    <xsl:if test="@alt and normalize-space(@alt) != ''">
      <xsl:value-of select="@alt"/>
    </xsl:if>
  </xsl:template>

  <!-- math: 出力しない（呼び出し側でdata-yomi付きspanに前処理済み） -->
  <xsl:template match="*:math"/>

  <!-- テキストノード: そのまま出力 -->
  <xsl:template match="text()">
    <xsl:value-of select="."/>
  </xsl:template>

  <!-- u, strong, sub, sup, em, span（data-yomiなし）:
       XSLTデフォルトテンプレートが子要素を再帰処理するため明示不要 -->

</xsl:stylesheet>
