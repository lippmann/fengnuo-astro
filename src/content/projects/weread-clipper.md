---
title: "剪阅"
subtitle: "一键将网页文章发送到微信读书"
description: "告别复制粘贴，任意网页文章一键生成 EPUB，直接出现在你的微信读书书架。"
type: "Chrome 扩展"
year: 2025
link: "https://chromewebstore.google.com/detail/ppcencmfnfiibooffeiddjdlbbfmcfop"
tags: ["Chrome 扩展", "微信读书", "EPUB"]
order: 1
icon: "/images/projects/weread-clipper/icon.png"
screenshots:
  - "/images/projects/weread-clipper/screen-2.png"
  - "/images/projects/weread-clipper/screen-3.png"
features:
  - title: "一键发送"
    desc: "打开文章页面，点击扩展图标，确认后即可发送。无需复制粘贴，无需手动制作文件。"
  - title: "智能提取正文"
    desc: "自动识别文章主体内容，过滤广告、导航栏、评论区等无关元素，适配主流中英文新闻和博客网站。"
  - title: "分页自动合并"
    desc: "遇到多页长文，自动依次抓取所有页面并合并成完整内容，一次发送，无需手动翻页。"
  - title: "图片完整保留"
    desc: "自动携带 Referer 绕过 CDN 防盗链，支持懒加载图片。图片以内嵌方式写入 EPUB，在微信读书中离线可见。"
  - title: "纯本地生成"
    desc: "所有处理均在本地完成，不收集任何用户数据，不向任何第三方服务器发送信息。"
steps:
  - "在 weread.qq.com 登录微信读书网页版（一次即可）"
  - "打开任意想保存的文章页面"
  - "点击工具栏中的扩展图标"
  - "确认标题，按需修改"
  - "点击「发送到微信读书」"
---

我是微信读书的重度用户，但有一个长期困扰：读到好的长文，想放进微信读书慢慢看，却没有好的办法。手动复制粘贴太麻烦，第三方工具要么需要登录、要么有广告、要么经常失效。

于是我花了几个周末，写了剪阅。
