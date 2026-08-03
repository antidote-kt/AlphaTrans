#!/usr/bin/env node
'use strict';

// ArkIR 负责调用语义，但不提供安全编辑源码所需的字符范围。
// ohos-typescript 是 Node.js 库，Python 不能直接调用，因此用这个 JS 作为 JSON 输入输出桥接层。
// 本文件只提取声明范围、标识符和 oh-package.json5，不负责生成调用图。

const fs = require('fs');
const ts = require(process.argv[2]);
const request = JSON.parse(fs.readFileSync(0, 'utf8'));

// 取得 AST 名称文本。
function nameText(name, sourceFile) {
  if (!name) return '<anonymous>';
  if (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name)) {
    return name.text;
  }
  return name.getText(sourceFile);
}

// 辅助函数：处理 identifiers。
function identifiers(node) {
  // 收集声明子树中的标识符，用于判断某个方法或类是否直接引用第三方 import 的本地名称。
  const values = new Set();
// 辅助函数：处理 visit。
  function visit(current) {
    if (ts.isIdentifier(current)) values.add(current.text);
    ts.forEachChild(current, visit);
  }
  if (node) visit(node);
  return [...values].sort();
}

// 辅助函数：处理 declarationStart。
function declarationStart(node, sourceFile) {
  return node.getStart(sourceFile, false);
}

// 辅助函数：处理 methodKind。
function methodKind(node) {
  if (ts.isConstructorDeclaration(node)) return 'constructor';
  if (ts.isGetAccessorDeclaration(node)) return 'getter';
  if (ts.isSetAccessorDeclaration(node)) return 'setter';
  return 'method';
}

// 辅助函数：处理 hasModifier。
function hasModifier(node, kind) {
  return Boolean(node.modifiers && node.modifiers.some((item) => item.kind === kind));
}

// 扫描源码文件的顶层声明。
function scanFile(filePath) {
  // ArkTS 的 .ets 语法由 ohos-typescript 按 TS AST 读取；只输出裁剪阶段需要的最小信息。
  const text = fs.readFileSync(filePath, 'utf8');
  const sourceFile = ts.createSourceFile(filePath, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const declarations = [];
  const classes = [];

  for (const statement of sourceFile.statements) {
    if (ts.isClassDeclaration(statement)) {
      const className = nameText(statement.name, sourceFile);
      const classIdentifiers = new Set();
      if (statement.decorators) {
        for (const decorator of statement.decorators) {
          identifiers(decorator).forEach((item) => classIdentifiers.add(item));
        }
      }
      if (statement.heritageClauses) {
        for (const heritage of statement.heritageClauses) {
          identifiers(heritage).forEach((item) => classIdentifiers.add(item));
        }
      }
      for (const member of statement.members) {
        if (ts.isPropertyDeclaration(member)) {
          identifiers(member).forEach((item) => classIdentifiers.add(item));
        }
      }
      classes.push({
        name: className,
        start: declarationStart(statement, sourceFile),
        end: statement.end,
        bodyStart: statement.members.pos,
        bodyEnd: statement.end - 1,
        identifiers: [...classIdentifiers].sort(),
        exported: hasModifier(statement, ts.SyntaxKind.ExportKeyword),
      });
      for (const member of statement.members) {
        if (!ts.isMethodDeclaration(member) && !ts.isConstructorDeclaration(member)
            && !ts.isGetAccessorDeclaration(member) && !ts.isSetAccessorDeclaration(member)) continue;
        const kind = methodKind(member);
        declarations.push({
          kind,
          className,
          name: kind === 'constructor' ? 'constructor' : nameText(member.name, sourceFile),
          start: declarationStart(member, sourceFile),
          end: member.end,
          identifiers: identifiers(member),
          override: hasModifier(member, ts.SyntaxKind.OverrideKeyword),
        });
      }
      continue;
    }

    if (ts.isFunctionDeclaration(statement) && statement.name) {
      declarations.push({
        kind: 'function',
        className: null,
        name: nameText(statement.name, sourceFile),
        start: declarationStart(statement, sourceFile),
        end: statement.end,
        identifiers: identifiers(statement),
        override: false,
      });
      continue;
    }

    if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (!declaration.initializer
            || (!ts.isArrowFunction(declaration.initializer)
                && !ts.isFunctionExpression(declaration.initializer))) continue;
        declarations.push({
          kind: 'function',
          className: null,
          name: nameText(declaration.name, sourceFile),
          start: declarationStart(statement, sourceFile),
          end: statement.end,
          identifiers: identifiers(statement),
          override: false,
        });
      }
    }
  }

  return {path: filePath, declarations, classes};
}

// 将 ohos-typescript 的 JSON5 AST 转成 Python 可读取的普通 JSON 值。
function jsonValue(node, sourceFile) {
  if (!node) return null;
  if (ts.isStringLiteral(node) || ts.isNumericLiteral(node)) return node.text;
  if (node.kind === ts.SyntaxKind.TrueKeyword) return true;
  if (node.kind === ts.SyntaxKind.FalseKeyword) return false;
  if (ts.isArrayLiteralExpression(node)) return node.elements.map((item) => jsonValue(item, sourceFile));
  if (ts.isObjectLiteralExpression(node)) {
    const value = {};
    for (const property of node.properties) {
      if (!ts.isPropertyAssignment(property)) continue;
      value[nameText(property.name, sourceFile)] = jsonValue(property.initializer, sourceFile);
    }
    return value;
  }
  return node.getText(sourceFile);
}

// 解析 JSON5 manifest。
function scanManifest(filePath) {
  // oh-package.json5 允许 JSON5 语法，不能假设它是严格 JSON。
  const text = fs.readFileSync(filePath, "utf8");
  const sourceFile = ts.parseJsonText(filePath, text);
  if (!sourceFile.statements.length) return {};
  return jsonValue(sourceFile.statements[0].expression, sourceFile) || {};
}

// Python 通过标准输入传入文件列表，本程序通过标准输出返回 JSON，不写中间文件。
const response = {files: [], manifests: {}};
response.files = (request.files || []).map(scanFile);
for (const manifest of request.manifests || []) response.manifests[manifest] = scanManifest(manifest);
process.stdout.write(JSON.stringify(response));
