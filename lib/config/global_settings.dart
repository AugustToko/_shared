/*
 * Project: tools_pack
 * Module: toolspack
 * Last Modified: 20-4-26 下午7:52
 * Copyright (c) 2020 August https://blog.geek-cloud.top/
 */

import 'package:flutter/services.dart';

/// 全局设置
class GlobalSettings {
  static String loginRouteName;
  static String profileRouteName;
  static String argPostsPageRouteName;
  static String appName;
  static MethodChannel channel;

  /// 模糊值
  static double blurSigma = 20.0;
}
