/*
 * Project: tools_pack
 * Module: toolspack
 * Last Modified: 20-4-25 下午10:44
 * Copyright (c) 2020 August https://blog.geek-cloud.top/
 */

import 'package:flutter/material.dart';

/// 主题工具
class ThemeUtil {
  static const double wpUserHeaderTextSize = 20.0;

  static Widget getLine({final Color color = Colors.black}) {
    return Container(
      color: color,
      height: 1,
    );
  }

  /// 获取用于放在 [AppBar] 上的方形按钮
  static Widget squareOutLineButtonOnAppBar(
      final String text, final Function() onTap, final Color color) {
    return Padding(
      padding: EdgeInsets.fromLTRB(0, 5, 10, 5),
      child: MaterialButton(
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(5),
            side: BorderSide(width: 1.5, color: color)),
        onPressed: onTap,
        child: Text(
          text,
          style: TextStyle(
            fontSize: 16,
            color: color,
          ),
        ),
      ),
    );
  }

  static var textOnDark =
      TextStyle(color: Colors.grey.shade50, fontFamily: "NotoSans");
  static var textOnLight =
      TextStyle(color: Colors.grey.shade900, fontFamily: "NotoSans");
  static var subtitle = TextStyle(color: Colors.grey, fontFamily: "NotoSans");

  static var clipRRectBorderRadius = BorderRadius.circular(8.0);

  static InputBorder getUnderlineFocusedBorderBorder(
          final BuildContext context) =>
      UnderlineInputBorder(
        borderSide: BorderSide(color: Theme.of(context).textTheme.title.color),
      );

  static InputBorder getUnderlineEnabledBorderBorder() =>
      UnderlineInputBorder(borderSide: BorderSide(color: Colors.grey));

  /// [NavBar]
  static double navBarHeight = 64;

  /// Editor编辑器 顶部图像
  /// [SendPage]
  static double headerImageHeight = 150;
}
