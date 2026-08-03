#!/usr/bin/env node
'use strict';

// ArkAnalyzer 提供 ArkIR 语义，本程序补充 ArkTS 源码声明、装饰器和精确位置。
// 输入和输出均为 JSON，不写中间文件。

const fs = require('fs');
const ts = require(process.argv[2]);
const request = JSON.parse(fs.readFileSync(0, 'utf8'));

// ohos-typescript 对 ArkTS 扩展节点仍通过 SyntaxKind 暴露，例如 StructDeclaration。
function nodeKind(node) {
  return ts.SyntaxKind[node.kind] || String(node.kind);
}

// 取得 AST 名称文本。
function nameText(name, sourceFile) {
  if (!name) return '<anonymous>';
  if (ts.isIdentifier(name) || ts.isStringLiteral(name) || ts.isNumericLiteral(name)) {
    return name.text;
  }
  return name.getText(sourceFile);
}

// 所有位置统一转换为 AlphaTrans 使用的一基行列；字符偏移保留给后续精确变换。
function rangeOf(node, sourceFile) {
  const start = node.getStart(sourceFile, false);
  const end = node.end;
  const startPosition = sourceFile.getLineAndCharacterOfPosition(start);
  const endPosition = sourceFile.getLineAndCharacterOfPosition(end);
  return {
    start,
    end,
    startLine: startPosition.line + 1,
    startColumn: startPosition.character + 1,
    endLine: endPosition.line + 1,
    endColumn: endPosition.character + 1,
  };
}

// ArkTS decorator 对应原 Java schema 中的 annotation 语义。
function decoratorsOf(node, sourceFile) {
  let decorators = [];
  if (typeof ts.canHaveDecorators === 'function' && ts.canHaveDecorators(node)) {
    decorators = ts.getDecorators(node) || [];
  } else if (node.decorators) {
    decorators = [...node.decorators];
  }
  return decorators.map((item) => item.getText(sourceFile));
}

// 提取声明 modifier。
function modifiersOf(node) {
  if (!node.modifiers) return [];
  return [...node.modifiers]
    .filter((item) => item.kind !== ts.SyntaxKind.Decorator)
    .map((item) => ts.tokenToString(item.kind) || nodeKind(item).replace(/Keyword$/, '').toLowerCase());
}

// 提取泛型参数。
function typeParametersOf(node, sourceFile) {
  return node.typeParameters ? [...node.typeParameters].map((item) => item.getText(sourceFile)) : [];
}

// 提取参数信息。
function parameterOf(parameter, sourceFile) {
  return {
    name: nameText(parameter.name, sourceFile),
    type: parameter.type ? parameter.type.getText(sourceFile) : 'unknown',
    optional: Boolean(parameter.questionToken || parameter.initializer),
    rest: Boolean(parameter.dotDotDotToken),
    default: parameter.initializer ? parameter.initializer.getText(sourceFile) : null,
    modifiers: modifiersOf(parameter),
    ...rangeOf(parameter, sourceFile),
  };
}

// 将 method/constructor/getter/setter/顶层 function 归一成同一 callable 结构。
function callableOf(node, sourceFile, className = null) {
  let kind = 'method';
  let name = nameText(node.name, sourceFile);
  if (ts.isConstructorDeclaration(node)) {
    kind = 'constructor';
    name = 'constructor';
  } else if (ts.isGetAccessorDeclaration(node)) {
    kind = 'getter';
  } else if (ts.isSetAccessorDeclaration(node)) {
    kind = 'setter';
  } else if (ts.isFunctionDeclaration(node)) {
    kind = 'function';
  }
  return {
    name,
    kind,
    className,
    signature: `${name}(${(node.parameters || []).map((item) => item.type ? item.type.getText(sourceFile) : 'unknown').join(', ')})`,
    parameters: (node.parameters || []).map((item) => parameterOf(item, sourceFile)),
    returnType: kind === 'constructor' ? 'void' : (node.type ? node.type.getText(sourceFile) : 'unknown'),
    modifiers: modifiersOf(node),
    decorators: decoratorsOf(node, sourceFile),
    typeParameters: typeParametersOf(node, sourceFile),
    hasBody: Boolean(node.body),
    ...rangeOf(node, sourceFile),
  };
}

// 提取字段信息。
function fieldOf(node, sourceFile) {
  const kind = ts.isEnumMember(node) ? 'enum_member' : 'field';
  return {
    name: nameText(node.name, sourceFile),
    kind,
    type: node.type ? node.type.getText(sourceFile) : 'unknown',
    initializer: node.initializer ? node.initializer.getText(sourceFile) : null,
    optional: Boolean(node.questionToken),
    definite: Boolean(node.exclamationToken),
    modifiers: modifiersOf(node),
    decorators: decoratorsOf(node, sourceFile),
    ...rangeOf(node, sourceFile),
  };
}

// 判断 class-like 节点类型。
function classKind(node) {
  if (ts.isInterfaceDeclaration(node)) return 'interface';
  if (ts.isEnumDeclaration(node)) return 'enum';
  if (nodeKind(node) === 'StructDeclaration') return 'struct';
  return 'class';
}

// class/interface/struct/enum 共用声明结构，kind 字段保留 ArkTS 的实际类别。
function classLikeOf(node, sourceFile, nestedInside = null) {
  const kind = classKind(node);
  const fields = [];
  const methods = [];
  const staticInitializers = [];
  const members = node.members || [];
  for (const member of members) {
    if (ts.isPropertyDeclaration(member) || ts.isPropertySignature(member) || ts.isEnumMember(member)) {
      fields.push(fieldOf(member, sourceFile));
    } else if (ts.isMethodDeclaration(member) || ts.isMethodSignature(member)
        || ts.isConstructorDeclaration(member) || ts.isGetAccessorDeclaration(member)
        || ts.isSetAccessorDeclaration(member)) {
      methods.push(callableOf(member, sourceFile, nameText(node.name, sourceFile)));
    } else if (nodeKind(member) === 'ClassStaticBlockDeclaration') {
      staticInitializers.push({...rangeOf(member, sourceFile)});
    }
  }

  const extendsNames = [];
  const implementsNames = [];
  for (const clause of node.heritageClauses || []) {
    const names = clause.types.map((item) => item.getText(sourceFile));
    if (clause.token === ts.SyntaxKind.ImplementsKeyword) implementsNames.push(...names);
    else extendsNames.push(...names);
  }

  return {
    name: nameText(node.name, sourceFile),
    kind,
    modifiers: modifiersOf(node),
    decorators: decoratorsOf(node, sourceFile),
    typeParameters: typeParametersOf(node, sourceFile),
    isAbstract: modifiersOf(node).includes('abstract'),
    nestedInside,
    extends: extendsNames,
    implements: implementsNames,
    fields,
    methods,
    staticInitializers,
    ...rangeOf(node, sourceFile),
  };
}

// Java 没有对应的文件级变量字段；ArkTS 顶层 const/let/var 单独记录。
function variableOf(statement, declaration, sourceFile) {
  const flags = statement.declarationList.flags;
  let declarationKind = 'var';
  if (flags & ts.NodeFlags.Const) declarationKind = 'const';
  else if (flags & ts.NodeFlags.Let) declarationKind = 'let';
  return {
    name: nameText(declaration.name, sourceFile),
    kind: declarationKind,
    type: declaration.type ? declaration.type.getText(sourceFile) : 'unknown',
    initializer: declaration.initializer ? declaration.initializer.getText(sourceFile) : null,
    modifiers: modifiersOf(statement),
    decorators: decoratorsOf(statement, sourceFile),
    ...rangeOf(statement, sourceFile),
  };
}

// 提取 import 声明信息。
function importOf(statement, sourceFile) {
  return {
    module: statement.moduleSpecifier.text,
    clause: statement.importClause ? statement.importClause.getText(sourceFile) : '',
    body: statement.getText(sourceFile),
    sideEffectOnly: !statement.importClause,
    ...rangeOf(statement, sourceFile),
  };
}

// 只扫描顶层声明；类成员由 classLikeOf 处理，函数体语义交给 ArkAnalyzer ArkIR。
function scanFile(filePath) {
  const text = fs.readFileSync(filePath, 'utf8');
  const sourceFile = ts.createSourceFile(filePath, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
  const result = {
    path: filePath,
    imports: [],
    exports: [],
    classes: [],
    functions: [],
    variables: [],
    typeAliases: [],
  };

  for (const statement of sourceFile.statements) {
    if (ts.isImportDeclaration(statement)) {
      result.imports.push(importOf(statement, sourceFile));
      continue;
    }
    if (ts.isExportDeclaration(statement) || ts.isExportAssignment(statement)) {
      result.exports.push({body: statement.getText(sourceFile), ...rangeOf(statement, sourceFile)});
      continue;
    }
    if (ts.isClassDeclaration(statement) || ts.isInterfaceDeclaration(statement)
        || ts.isEnumDeclaration(statement) || nodeKind(statement) === 'StructDeclaration') {
      const item = classLikeOf(statement, sourceFile);
      result.classes.push(item);
      if (item.modifiers.includes('export') || item.modifiers.includes('default')) {
        result.exports.push({name: item.name, kind: item.kind, default: item.modifiers.includes('default')});
      }
      continue;
    }
    if (ts.isFunctionDeclaration(statement) && statement.name) {
      const item = callableOf(statement, sourceFile, null);
      result.functions.push(item);
      if (item.modifiers.includes('export') || item.modifiers.includes('default')) {
        result.exports.push({name: item.name, kind: 'function', default: item.modifiers.includes('default')});
      }
      continue;
    }
    if (ts.isTypeAliasDeclaration(statement)) {
      result.typeAliases.push({
        name: nameText(statement.name, sourceFile),
        kind: 'type_alias',
        type: statement.type.getText(sourceFile),
        modifiers: modifiersOf(statement),
        typeParameters: typeParametersOf(statement, sourceFile),
        ...rangeOf(statement, sourceFile),
      });
      continue;
    }
    // 箭头函数和函数表达式在 AST 中属于变量声明，但 schema 中应视作顶层 callable。
    if (ts.isVariableStatement(statement)) {
      for (const declaration of statement.declarationList.declarations) {
        if (declaration.initializer
            && (ts.isArrowFunction(declaration.initializer) || ts.isFunctionExpression(declaration.initializer))) {
          const callable = callableOf(declaration.initializer, sourceFile, null);
          callable.name = nameText(declaration.name, sourceFile);
          callable.signature = `${callable.name}(${callable.parameters.map((item) => item.type).join(', ')})`;
          callable.start = rangeOf(statement, sourceFile).start;
          callable.startLine = rangeOf(statement, sourceFile).startLine;
          callable.startColumn = rangeOf(statement, sourceFile).startColumn;
          callable.end = rangeOf(statement, sourceFile).end;
          callable.endLine = rangeOf(statement, sourceFile).endLine;
          callable.endColumn = rangeOf(statement, sourceFile).endColumn;
          callable.modifiers = modifiersOf(statement);
          result.functions.push(callable);
        } else {
          result.variables.push(variableOf(statement, declaration, sourceFile));
        }
      }
    }
  }
  return result;
}

process.stdout.write(JSON.stringify({files: (request.files || []).map(scanFile)}));
