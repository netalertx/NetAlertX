"use strict";
var Treeviz = (() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
  var __hasOwnProp = Object.prototype.hasOwnProperty;
  var __name = (target, value) => __defProp(target, "name", { value, configurable: true });
  var __export = (target, all) => {
    for (var name in all)
      __defProp(target, name, { get: all[name], enumerable: true });
  };
  var __copyProps = (to, from, except, desc) => {
    if (from && typeof from === "object" || typeof from === "function") {
      for (let key of __getOwnPropNames(from))
        if (!__hasOwnProp.call(to, key) && key !== except)
          __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
    }
    return to;
  };
  var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

  // src/index.ts
  var index_exports = {};
  __export(index_exports, {
    Treeviz: () => Treeviz,
    create: () => create2
  });

  // node_modules/d3-hierarchy/src/hierarchy/count.js
  function count(node) {
    var sum = 0, children2 = node.children, i = children2 && children2.length;
    if (!i) sum = 1;
    else while (--i >= 0) sum += children2[i].value;
    node.value = sum;
  }
  __name(count, "count");
  function count_default() {
    return this.eachAfter(count);
  }
  __name(count_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/each.js
  function each_default(callback, that) {
    let index = -1;
    for (const node of this) {
      callback.call(that, node, ++index, this);
    }
    return this;
  }
  __name(each_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/eachBefore.js
  function eachBefore_default(callback, that) {
    var node = this, nodes = [node], children2, i, index = -1;
    while (node = nodes.pop()) {
      callback.call(that, node, ++index, this);
      if (children2 = node.children) {
        for (i = children2.length - 1; i >= 0; --i) {
          nodes.push(children2[i]);
        }
      }
    }
    return this;
  }
  __name(eachBefore_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/eachAfter.js
  function eachAfter_default(callback, that) {
    var node = this, nodes = [node], next = [], children2, i, n, index = -1;
    while (node = nodes.pop()) {
      next.push(node);
      if (children2 = node.children) {
        for (i = 0, n = children2.length; i < n; ++i) {
          nodes.push(children2[i]);
        }
      }
    }
    while (node = next.pop()) {
      callback.call(that, node, ++index, this);
    }
    return this;
  }
  __name(eachAfter_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/find.js
  function find_default(callback, that) {
    let index = -1;
    for (const node of this) {
      if (callback.call(that, node, ++index, this)) {
        return node;
      }
    }
  }
  __name(find_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/sum.js
  function sum_default(value) {
    return this.eachAfter(function(node) {
      var sum = +value(node.data) || 0, children2 = node.children, i = children2 && children2.length;
      while (--i >= 0) sum += children2[i].value;
      node.value = sum;
    });
  }
  __name(sum_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/sort.js
  function sort_default(compare) {
    return this.eachBefore(function(node) {
      if (node.children) {
        node.children.sort(compare);
      }
    });
  }
  __name(sort_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/path.js
  function path_default(end) {
    var start2 = this, ancestor = leastCommonAncestor(start2, end), nodes = [start2];
    while (start2 !== ancestor) {
      start2 = start2.parent;
      nodes.push(start2);
    }
    var k = nodes.length;
    while (end !== ancestor) {
      nodes.splice(k, 0, end);
      end = end.parent;
    }
    return nodes;
  }
  __name(path_default, "default");
  function leastCommonAncestor(a, b) {
    if (a === b) return a;
    var aNodes = a.ancestors(), bNodes = b.ancestors(), c = null;
    a = aNodes.pop();
    b = bNodes.pop();
    while (a === b) {
      c = a;
      a = aNodes.pop();
      b = bNodes.pop();
    }
    return c;
  }
  __name(leastCommonAncestor, "leastCommonAncestor");

  // node_modules/d3-hierarchy/src/hierarchy/ancestors.js
  function ancestors_default() {
    var node = this, nodes = [node];
    while (node = node.parent) {
      nodes.push(node);
    }
    return nodes;
  }
  __name(ancestors_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/descendants.js
  function descendants_default() {
    return Array.from(this);
  }
  __name(descendants_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/leaves.js
  function leaves_default() {
    var leaves = [];
    this.eachBefore(function(node) {
      if (!node.children) {
        leaves.push(node);
      }
    });
    return leaves;
  }
  __name(leaves_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/links.js
  function links_default() {
    var root2 = this, links = [];
    root2.each(function(node) {
      if (node !== root2) {
        links.push({ source: node.parent, target: node });
      }
    });
    return links;
  }
  __name(links_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/iterator.js
  function* iterator_default() {
    var node = this, current, next = [node], children2, i, n;
    do {
      current = next.reverse(), next = [];
      while (node = current.pop()) {
        yield node;
        if (children2 = node.children) {
          for (i = 0, n = children2.length; i < n; ++i) {
            next.push(children2[i]);
          }
        }
      }
    } while (next.length);
  }
  __name(iterator_default, "default");

  // node_modules/d3-hierarchy/src/hierarchy/index.js
  function hierarchy(data, children2) {
    if (data instanceof Map) {
      data = [void 0, data];
      if (children2 === void 0) children2 = mapChildren;
    } else if (children2 === void 0) {
      children2 = objectChildren;
    }
    var root2 = new Node(data), node, nodes = [root2], child, childs, i, n;
    while (node = nodes.pop()) {
      if ((childs = children2(node.data)) && (n = (childs = Array.from(childs)).length)) {
        node.children = childs;
        for (i = n - 1; i >= 0; --i) {
          nodes.push(child = childs[i] = new Node(childs[i]));
          child.parent = node;
          child.depth = node.depth + 1;
        }
      }
    }
    return root2.eachBefore(computeHeight);
  }
  __name(hierarchy, "hierarchy");
  function node_copy() {
    return hierarchy(this).eachBefore(copyData);
  }
  __name(node_copy, "node_copy");
  function objectChildren(d) {
    return d.children;
  }
  __name(objectChildren, "objectChildren");
  function mapChildren(d) {
    return Array.isArray(d) ? d[1] : null;
  }
  __name(mapChildren, "mapChildren");
  function copyData(node) {
    if (node.data.value !== void 0) node.value = node.data.value;
    node.data = node.data.data;
  }
  __name(copyData, "copyData");
  function computeHeight(node) {
    var height = 0;
    do
      node.height = height;
    while ((node = node.parent) && node.height < ++height);
  }
  __name(computeHeight, "computeHeight");
  function Node(data) {
    this.data = data;
    this.depth = this.height = 0;
    this.parent = null;
  }
  __name(Node, "Node");
  Node.prototype = hierarchy.prototype = {
    constructor: Node,
    count: count_default,
    each: each_default,
    eachAfter: eachAfter_default,
    eachBefore: eachBefore_default,
    find: find_default,
    sum: sum_default,
    sort: sort_default,
    path: path_default,
    ancestors: ancestors_default,
    descendants: descendants_default,
    leaves: leaves_default,
    links: links_default,
    copy: node_copy,
    [Symbol.iterator]: iterator_default
  };

  // node_modules/d3-hierarchy/src/accessors.js
  function optional(f) {
    return f == null ? null : required(f);
  }
  __name(optional, "optional");
  function required(f) {
    if (typeof f !== "function") throw new Error();
    return f;
  }
  __name(required, "required");

  // node_modules/d3-hierarchy/src/constant.js
  function constantZero() {
    return 0;
  }
  __name(constantZero, "constantZero");
  function constant_default(x) {
    return function() {
      return x;
    };
  }
  __name(constant_default, "default");

  // node_modules/d3-hierarchy/src/treemap/round.js
  function round_default(node) {
    node.x0 = Math.round(node.x0);
    node.y0 = Math.round(node.y0);
    node.x1 = Math.round(node.x1);
    node.y1 = Math.round(node.y1);
  }
  __name(round_default, "default");

  // node_modules/d3-hierarchy/src/treemap/dice.js
  function dice_default(parent, x0, y0, x1, y1) {
    var nodes = parent.children, node, i = -1, n = nodes.length, k = parent.value && (x1 - x0) / parent.value;
    while (++i < n) {
      node = nodes[i], node.y0 = y0, node.y1 = y1;
      node.x0 = x0, node.x1 = x0 += node.value * k;
    }
  }
  __name(dice_default, "default");

  // node_modules/d3-hierarchy/src/stratify.js
  var preroot = { depth: -1 };
  var ambiguous = {};
  var imputed = {};
  function defaultId(d) {
    return d.id;
  }
  __name(defaultId, "defaultId");
  function defaultParentId(d) {
    return d.parentId;
  }
  __name(defaultParentId, "defaultParentId");
  function stratify_default() {
    var id2 = defaultId, parentId = defaultParentId, path;
    function stratify(data) {
      var nodes = Array.from(data), currentId = id2, currentParentId = parentId, n, d, i, root2, parent, node, nodeId, nodeKey, nodeByKey = /* @__PURE__ */ new Map();
      if (path != null) {
        const I = nodes.map((d2, i2) => normalize(path(d2, i2, data)));
        const P = I.map(parentof);
        const S = new Set(I).add("");
        for (const i2 of P) {
          if (!S.has(i2)) {
            S.add(i2);
            I.push(i2);
            P.push(parentof(i2));
            nodes.push(imputed);
          }
        }
        currentId = /* @__PURE__ */ __name((_, i2) => I[i2], "currentId");
        currentParentId = /* @__PURE__ */ __name((_, i2) => P[i2], "currentParentId");
      }
      for (i = 0, n = nodes.length; i < n; ++i) {
        d = nodes[i], node = nodes[i] = new Node(d);
        if ((nodeId = currentId(d, i, data)) != null && (nodeId += "")) {
          nodeKey = node.id = nodeId;
          nodeByKey.set(nodeKey, nodeByKey.has(nodeKey) ? ambiguous : node);
        }
        if ((nodeId = currentParentId(d, i, data)) != null && (nodeId += "")) {
          node.parent = nodeId;
        }
      }
      for (i = 0; i < n; ++i) {
        node = nodes[i];
        if (nodeId = node.parent) {
          parent = nodeByKey.get(nodeId);
          if (!parent) throw new Error("missing: " + nodeId);
          if (parent === ambiguous) throw new Error("ambiguous: " + nodeId);
          if (parent.children) parent.children.push(node);
          else parent.children = [node];
          node.parent = parent;
        } else {
          if (root2) throw new Error("multiple roots");
          root2 = node;
        }
      }
      if (!root2) throw new Error("no root");
      if (path != null) {
        while (root2.data === imputed && root2.children.length === 1) {
          root2 = root2.children[0], --n;
        }
        for (let i2 = nodes.length - 1; i2 >= 0; --i2) {
          node = nodes[i2];
          if (node.data !== imputed) break;
          node.data = null;
        }
      }
      root2.parent = preroot;
      root2.eachBefore(function(node2) {
        node2.depth = node2.parent.depth + 1;
        --n;
      }).eachBefore(computeHeight);
      root2.parent = null;
      if (n > 0) throw new Error("cycle");
      return root2;
    }
    __name(stratify, "stratify");
    stratify.id = function(x) {
      return arguments.length ? (id2 = optional(x), stratify) : id2;
    };
    stratify.parentId = function(x) {
      return arguments.length ? (parentId = optional(x), stratify) : parentId;
    };
    stratify.path = function(x) {
      return arguments.length ? (path = optional(x), stratify) : path;
    };
    return stratify;
  }
  __name(stratify_default, "default");
  function normalize(path) {
    path = `${path}`;
    let i = path.length;
    if (slash(path, i - 1) && !slash(path, i - 2)) path = path.slice(0, -1);
    return path[0] === "/" ? path : `/${path}`;
  }
  __name(normalize, "normalize");
  function parentof(path) {
    let i = path.length;
    if (i < 2) return "";
    while (--i > 1) if (slash(path, i)) break;
    return path.slice(0, i);
  }
  __name(parentof, "parentof");
  function slash(path, i) {
    if (path[i] === "/") {
      let k = 0;
      while (i > 0 && path[--i] === "\\") ++k;
      if ((k & 1) === 0) return true;
    }
    return false;
  }
  __name(slash, "slash");

  // node_modules/d3-hierarchy/src/tree.js
  function defaultSeparation(a, b) {
    return a.parent === b.parent ? 1 : 2;
  }
  __name(defaultSeparation, "defaultSeparation");
  function nextLeft(v) {
    var children2 = v.children;
    return children2 ? children2[0] : v.t;
  }
  __name(nextLeft, "nextLeft");
  function nextRight(v) {
    var children2 = v.children;
    return children2 ? children2[children2.length - 1] : v.t;
  }
  __name(nextRight, "nextRight");
  function moveSubtree(wm, wp, shift) {
    var change = shift / (wp.i - wm.i);
    wp.c -= change;
    wp.s += shift;
    wm.c += change;
    wp.z += shift;
    wp.m += shift;
  }
  __name(moveSubtree, "moveSubtree");
  function executeShifts(v) {
    var shift = 0, change = 0, children2 = v.children, i = children2.length, w;
    while (--i >= 0) {
      w = children2[i];
      w.z += shift;
      w.m += shift;
      shift += w.s + (change += w.c);
    }
  }
  __name(executeShifts, "executeShifts");
  function nextAncestor(vim, v, ancestor) {
    return vim.a.parent === v.parent ? vim.a : ancestor;
  }
  __name(nextAncestor, "nextAncestor");
  function TreeNode(node, i) {
    this._ = node;
    this.parent = null;
    this.children = null;
    this.A = null;
    this.a = this;
    this.z = 0;
    this.m = 0;
    this.c = 0;
    this.s = 0;
    this.t = null;
    this.i = i;
  }
  __name(TreeNode, "TreeNode");
  TreeNode.prototype = Object.create(Node.prototype);
  function treeRoot(root2) {
    var tree = new TreeNode(root2, 0), node, nodes = [tree], child, children2, i, n;
    while (node = nodes.pop()) {
      if (children2 = node._.children) {
        node.children = new Array(n = children2.length);
        for (i = n - 1; i >= 0; --i) {
          nodes.push(child = node.children[i] = new TreeNode(children2[i], i));
          child.parent = node;
        }
      }
    }
    (tree.parent = new TreeNode(null, 0)).children = [tree];
    return tree;
  }
  __name(treeRoot, "treeRoot");
  function tree_default() {
    var separation = defaultSeparation, dx = 1, dy = 1, nodeSize = null;
    function tree(root2) {
      var t = treeRoot(root2);
      t.eachAfter(firstWalk), t.parent.m = -t.z;
      t.eachBefore(secondWalk);
      if (nodeSize) root2.eachBefore(sizeNode);
      else {
        var left = root2, right = root2, bottom = root2;
        root2.eachBefore(function(node) {
          if (node.x < left.x) left = node;
          if (node.x > right.x) right = node;
          if (node.depth > bottom.depth) bottom = node;
        });
        var s = left === right ? 1 : separation(left, right) / 2, tx = s - left.x, kx = dx / (right.x + s + tx), ky = dy / (bottom.depth || 1);
        root2.eachBefore(function(node) {
          node.x = (node.x + tx) * kx;
          node.y = node.depth * ky;
        });
      }
      return root2;
    }
    __name(tree, "tree");
    function firstWalk(v) {
      var children2 = v.children, siblings = v.parent.children, w = v.i ? siblings[v.i - 1] : null;
      if (children2) {
        executeShifts(v);
        var midpoint = (children2[0].z + children2[children2.length - 1].z) / 2;
        if (w) {
          v.z = w.z + separation(v._, w._);
          v.m = v.z - midpoint;
        } else {
          v.z = midpoint;
        }
      } else if (w) {
        v.z = w.z + separation(v._, w._);
      }
      v.parent.A = apportion(v, w, v.parent.A || siblings[0]);
    }
    __name(firstWalk, "firstWalk");
    function secondWalk(v) {
      v._.x = v.z + v.parent.m;
      v.m += v.parent.m;
    }
    __name(secondWalk, "secondWalk");
    function apportion(v, w, ancestor) {
      if (w) {
        var vip = v, vop = v, vim = w, vom = vip.parent.children[0], sip = vip.m, sop = vop.m, sim = vim.m, som = vom.m, shift;
        while (vim = nextRight(vim), vip = nextLeft(vip), vim && vip) {
          vom = nextLeft(vom);
          vop = nextRight(vop);
          vop.a = v;
          shift = vim.z + sim - vip.z - sip + separation(vim._, vip._);
          if (shift > 0) {
            moveSubtree(nextAncestor(vim, v, ancestor), v, shift);
            sip += shift;
            sop += shift;
          }
          sim += vim.m;
          sip += vip.m;
          som += vom.m;
          sop += vop.m;
        }
        if (vim && !nextRight(vop)) {
          vop.t = vim;
          vop.m += sim - sop;
        }
        if (vip && !nextLeft(vom)) {
          vom.t = vip;
          vom.m += sip - som;
          ancestor = v;
        }
      }
      return ancestor;
    }
    __name(apportion, "apportion");
    function sizeNode(node) {
      node.x *= dx;
      node.y = node.depth * dy;
    }
    __name(sizeNode, "sizeNode");
    tree.separation = function(x) {
      return arguments.length ? (separation = x, tree) : separation;
    };
    tree.size = function(x) {
      return arguments.length ? (nodeSize = false, dx = +x[0], dy = +x[1], tree) : nodeSize ? null : [dx, dy];
    };
    tree.nodeSize = function(x) {
      return arguments.length ? (nodeSize = true, dx = +x[0], dy = +x[1], tree) : nodeSize ? [dx, dy] : null;
    };
    return tree;
  }
  __name(tree_default, "default");

  // node_modules/d3-hierarchy/src/treemap/slice.js
  function slice_default(parent, x0, y0, x1, y1) {
    var nodes = parent.children, node, i = -1, n = nodes.length, k = parent.value && (y1 - y0) / parent.value;
    while (++i < n) {
      node = nodes[i], node.x0 = x0, node.x1 = x1;
      node.y0 = y0, node.y1 = y0 += node.value * k;
    }
  }
  __name(slice_default, "default");

  // node_modules/d3-hierarchy/src/treemap/squarify.js
  var phi = (1 + Math.sqrt(5)) / 2;
  function squarifyRatio(ratio, parent, x0, y0, x1, y1) {
    var rows = [], nodes = parent.children, row, nodeValue, i0 = 0, i1 = 0, n = nodes.length, dx, dy, value = parent.value, sumValue, minValue, maxValue, newRatio, minRatio, alpha, beta;
    while (i0 < n) {
      dx = x1 - x0, dy = y1 - y0;
      do
        sumValue = nodes[i1++].value;
      while (!sumValue && i1 < n);
      minValue = maxValue = sumValue;
      alpha = Math.max(dy / dx, dx / dy) / (value * ratio);
      beta = sumValue * sumValue * alpha;
      minRatio = Math.max(maxValue / beta, beta / minValue);
      for (; i1 < n; ++i1) {
        sumValue += nodeValue = nodes[i1].value;
        if (nodeValue < minValue) minValue = nodeValue;
        if (nodeValue > maxValue) maxValue = nodeValue;
        beta = sumValue * sumValue * alpha;
        newRatio = Math.max(maxValue / beta, beta / minValue);
        if (newRatio > minRatio) {
          sumValue -= nodeValue;
          break;
        }
        minRatio = newRatio;
      }
      rows.push(row = { value: sumValue, dice: dx < dy, children: nodes.slice(i0, i1) });
      if (row.dice) dice_default(row, x0, y0, x1, value ? y0 += dy * sumValue / value : y1);
      else slice_default(row, x0, y0, value ? x0 += dx * sumValue / value : x1, y1);
      value -= sumValue, i0 = i1;
    }
    return rows;
  }
  __name(squarifyRatio, "squarifyRatio");
  var squarify_default = (/* @__PURE__ */ __name(function custom(ratio) {
    function squarify(parent, x0, y0, x1, y1) {
      squarifyRatio(ratio, parent, x0, y0, x1, y1);
    }
    __name(squarify, "squarify");
    squarify.ratio = function(x) {
      return custom((x = +x) > 1 ? x : 1);
    };
    return squarify;
  }, "custom"))(phi);

  // node_modules/d3-hierarchy/src/treemap/index.js
  function treemap_default() {
    var tile = squarify_default, round = false, dx = 1, dy = 1, paddingStack = [0], paddingInner = constantZero, paddingTop = constantZero, paddingRight = constantZero, paddingBottom = constantZero, paddingLeft = constantZero;
    function treemap(root2) {
      root2.x0 = root2.y0 = 0;
      root2.x1 = dx;
      root2.y1 = dy;
      root2.eachBefore(positionNode);
      paddingStack = [0];
      if (round) root2.eachBefore(round_default);
      return root2;
    }
    __name(treemap, "treemap");
    function positionNode(node) {
      var p = paddingStack[node.depth], x0 = node.x0 + p, y0 = node.y0 + p, x1 = node.x1 - p, y1 = node.y1 - p;
      if (x1 < x0) x0 = x1 = (x0 + x1) / 2;
      if (y1 < y0) y0 = y1 = (y0 + y1) / 2;
      node.x0 = x0;
      node.y0 = y0;
      node.x1 = x1;
      node.y1 = y1;
      if (node.children) {
        p = paddingStack[node.depth + 1] = paddingInner(node) / 2;
        x0 += paddingLeft(node) - p;
        y0 += paddingTop(node) - p;
        x1 -= paddingRight(node) - p;
        y1 -= paddingBottom(node) - p;
        if (x1 < x0) x0 = x1 = (x0 + x1) / 2;
        if (y1 < y0) y0 = y1 = (y0 + y1) / 2;
        tile(node, x0, y0, x1, y1);
      }
    }
    __name(positionNode, "positionNode");
    treemap.round = function(x) {
      return arguments.length ? (round = !!x, treemap) : round;
    };
    treemap.size = function(x) {
      return arguments.length ? (dx = +x[0], dy = +x[1], treemap) : [dx, dy];
    };
    treemap.tile = function(x) {
      return arguments.length ? (tile = required(x), treemap) : tile;
    };
    treemap.padding = function(x) {
      return arguments.length ? treemap.paddingInner(x).paddingOuter(x) : treemap.paddingInner();
    };
    treemap.paddingInner = function(x) {
      return arguments.length ? (paddingInner = typeof x === "function" ? x : constant_default(+x), treemap) : paddingInner;
    };
    treemap.paddingOuter = function(x) {
      return arguments.length ? treemap.paddingTop(x).paddingRight(x).paddingBottom(x).paddingLeft(x) : treemap.paddingTop();
    };
    treemap.paddingTop = function(x) {
      return arguments.length ? (paddingTop = typeof x === "function" ? x : constant_default(+x), treemap) : paddingTop;
    };
    treemap.paddingRight = function(x) {
      return arguments.length ? (paddingRight = typeof x === "function" ? x : constant_default(+x), treemap) : paddingRight;
    };
    treemap.paddingBottom = function(x) {
      return arguments.length ? (paddingBottom = typeof x === "function" ? x : constant_default(+x), treemap) : paddingBottom;
    };
    treemap.paddingLeft = function(x) {
      return arguments.length ? (paddingLeft = typeof x === "function" ? x : constant_default(+x), treemap) : paddingLeft;
    };
    return treemap;
  }
  __name(treemap_default, "default");

  // node_modules/d3-selection/src/namespaces.js
  var xhtml = "http://www.w3.org/1999/xhtml";
  var namespaces_default = {
    svg: "http://www.w3.org/2000/svg",
    xhtml,
    xlink: "http://www.w3.org/1999/xlink",
    xml: "http://www.w3.org/XML/1998/namespace",
    xmlns: "http://www.w3.org/2000/xmlns/"
  };

  // node_modules/d3-selection/src/namespace.js
  function namespace_default(name) {
    var prefix = name += "", i = prefix.indexOf(":");
    if (i >= 0 && (prefix = name.slice(0, i)) !== "xmlns") name = name.slice(i + 1);
    return namespaces_default.hasOwnProperty(prefix) ? { space: namespaces_default[prefix], local: name } : name;
  }
  __name(namespace_default, "default");

  // node_modules/d3-selection/src/creator.js
  function creatorInherit(name) {
    return function() {
      var document2 = this.ownerDocument, uri = this.namespaceURI;
      return uri === xhtml && document2.documentElement.namespaceURI === xhtml ? document2.createElement(name) : document2.createElementNS(uri, name);
    };
  }
  __name(creatorInherit, "creatorInherit");
  function creatorFixed(fullname) {
    return function() {
      return this.ownerDocument.createElementNS(fullname.space, fullname.local);
    };
  }
  __name(creatorFixed, "creatorFixed");
  function creator_default(name) {
    var fullname = namespace_default(name);
    return (fullname.local ? creatorFixed : creatorInherit)(fullname);
  }
  __name(creator_default, "default");

  // node_modules/d3-selection/src/selector.js
  function none() {
  }
  __name(none, "none");
  function selector_default(selector) {
    return selector == null ? none : function() {
      return this.querySelector(selector);
    };
  }
  __name(selector_default, "default");

  // node_modules/d3-selection/src/selection/select.js
  function select_default(select) {
    if (typeof select !== "function") select = selector_default(select);
    for (var groups = this._groups, m = groups.length, subgroups = new Array(m), j = 0; j < m; ++j) {
      for (var group = groups[j], n = group.length, subgroup = subgroups[j] = new Array(n), node, subnode, i = 0; i < n; ++i) {
        if ((node = group[i]) && (subnode = select.call(node, node.__data__, i, group))) {
          if ("__data__" in node) subnode.__data__ = node.__data__;
          subgroup[i] = subnode;
        }
      }
    }
    return new Selection(subgroups, this._parents);
  }
  __name(select_default, "default");

  // node_modules/d3-selection/src/array.js
  function array(x) {
    return x == null ? [] : Array.isArray(x) ? x : Array.from(x);
  }
  __name(array, "array");

  // node_modules/d3-selection/src/selectorAll.js
  function empty() {
    return [];
  }
  __name(empty, "empty");
  function selectorAll_default(selector) {
    return selector == null ? empty : function() {
      return this.querySelectorAll(selector);
    };
  }
  __name(selectorAll_default, "default");

  // node_modules/d3-selection/src/selection/selectAll.js
  function arrayAll(select) {
    return function() {
      return array(select.apply(this, arguments));
    };
  }
  __name(arrayAll, "arrayAll");
  function selectAll_default(select) {
    if (typeof select === "function") select = arrayAll(select);
    else select = selectorAll_default(select);
    for (var groups = this._groups, m = groups.length, subgroups = [], parents = [], j = 0; j < m; ++j) {
      for (var group = groups[j], n = group.length, node, i = 0; i < n; ++i) {
        if (node = group[i]) {
          subgroups.push(select.call(node, node.__data__, i, group));
          parents.push(node);
        }
      }
    }
    return new Selection(subgroups, parents);
  }
  __name(selectAll_default, "default");

  // node_modules/d3-selection/src/matcher.js
  function matcher_default(selector) {
    return function() {
      return this.matches(selector);
    };
  }
  __name(matcher_default, "default");
  function childMatcher(selector) {
    return function(node) {
      return node.matches(selector);
    };
  }
  __name(childMatcher, "childMatcher");

  // node_modules/d3-selection/src/selection/selectChild.js
  var find = Array.prototype.find;
  function childFind(match) {
    return function() {
      return find.call(this.children, match);
    };
  }
  __name(childFind, "childFind");
  function childFirst() {
    return this.firstElementChild;
  }
  __name(childFirst, "childFirst");
  function selectChild_default(match) {
    return this.select(match == null ? childFirst : childFind(typeof match === "function" ? match : childMatcher(match)));
  }
  __name(selectChild_default, "default");

  // node_modules/d3-selection/src/selection/selectChildren.js
  var filter = Array.prototype.filter;
  function children() {
    return Array.from(this.children);
  }
  __name(children, "children");
  function childrenFilter(match) {
    return function() {
      return filter.call(this.children, match);
    };
  }
  __name(childrenFilter, "childrenFilter");
  function selectChildren_default(match) {
    return this.selectAll(match == null ? children : childrenFilter(typeof match === "function" ? match : childMatcher(match)));
  }
  __name(selectChildren_default, "default");

  // node_modules/d3-selection/src/selection/filter.js
  function filter_default(match) {
    if (typeof match !== "function") match = matcher_default(match);
    for (var groups = this._groups, m = groups.length, subgroups = new Array(m), j = 0; j < m; ++j) {
      for (var group = groups[j], n = group.length, subgroup = subgroups[j] = [], node, i = 0; i < n; ++i) {
        if ((node = group[i]) && match.call(node, node.__data__, i, group)) {
          subgroup.push(node);
        }
      }
    }
    return new Selection(subgroups, this._parents);
  }
  __name(filter_default, "default");

  // node_modules/d3-selection/src/selection/sparse.js
  function sparse_default(update) {
    return new Array(update.length);
  }
  __name(sparse_default, "default");

  // node_modules/d3-selection/src/selection/enter.js
  function enter_default() {
    return new Selection(this._enter || this._groups.map(sparse_default), this._parents);
  }
  __name(enter_default, "default");
  function EnterNode(parent, datum2) {
    this.ownerDocument = parent.ownerDocument;
    this.namespaceURI = parent.namespaceURI;
    this._next = null;
    this._parent = parent;
    this.__data__ = datum2;
  }
  __name(EnterNode, "EnterNode");
  EnterNode.prototype = {
    constructor: EnterNode,
    appendChild: /* @__PURE__ */ __name(function(child) {
      return this._parent.insertBefore(child, this._next);
    }, "appendChild"),
    insertBefore: /* @__PURE__ */ __name(function(child, next) {
      return this._parent.insertBefore(child, next);
    }, "insertBefore"),
    querySelector: /* @__PURE__ */ __name(function(selector) {
      return this._parent.querySelector(selector);
    }, "querySelector"),
    querySelectorAll: /* @__PURE__ */ __name(function(selector) {
      return this._parent.querySelectorAll(selector);
    }, "querySelectorAll")
  };

  // node_modules/d3-selection/src/constant.js
  function constant_default2(x) {
    return function() {
      return x;
    };
  }
  __name(constant_default2, "default");

  // node_modules/d3-selection/src/selection/data.js
  function bindIndex(parent, group, enter, update, exit, data) {
    var i = 0, node, groupLength = group.length, dataLength = data.length;
    for (; i < dataLength; ++i) {
      if (node = group[i]) {
        node.__data__ = data[i];
        update[i] = node;
      } else {
        enter[i] = new EnterNode(parent, data[i]);
      }
    }
    for (; i < groupLength; ++i) {
      if (node = group[i]) {
        exit[i] = node;
      }
    }
  }
  __name(bindIndex, "bindIndex");
  function bindKey(parent, group, enter, update, exit, data, key) {
    var i, node, nodeByKeyValue = /* @__PURE__ */ new Map(), groupLength = group.length, dataLength = data.length, keyValues = new Array(groupLength), keyValue;
    for (i = 0; i < groupLength; ++i) {
      if (node = group[i]) {
        keyValues[i] = keyValue = key.call(node, node.__data__, i, group) + "";
        if (nodeByKeyValue.has(keyValue)) {
          exit[i] = node;
        } else {
          nodeByKeyValue.set(keyValue, node);
        }
      }
    }
    for (i = 0; i < dataLength; ++i) {
      keyValue = key.call(parent, data[i], i, data) + "";
      if (node = nodeByKeyValue.get(keyValue)) {
        update[i] = node;
        node.__data__ = data[i];
        nodeByKeyValue.delete(keyValue);
      } else {
        enter[i] = new EnterNode(parent, data[i]);
      }
    }
    for (i = 0; i < groupLength; ++i) {
      if ((node = group[i]) && nodeByKeyValue.get(keyValues[i]) === node) {
        exit[i] = node;
      }
    }
  }
  __name(bindKey, "bindKey");
  function datum(node) {
    return node.__data__;
  }
  __name(datum, "datum");
  function data_default(value, key) {
    if (!arguments.length) return Array.from(this, datum);
    var bind = key ? bindKey : bindIndex, parents = this._parents, groups = this._groups;
    if (typeof value !== "function") value = constant_default2(value);
    for (var m = groups.length, update = new Array(m), enter = new Array(m), exit = new Array(m), j = 0; j < m; ++j) {
      var parent = parents[j], group = groups[j], groupLength = group.length, data = arraylike(value.call(parent, parent && parent.__data__, j, parents)), dataLength = data.length, enterGroup = enter[j] = new Array(dataLength), updateGroup = update[j] = new Array(dataLength), exitGroup = exit[j] = new Array(groupLength);
      bind(parent, group, enterGroup, updateGroup, exitGroup, data, key);
      for (var i0 = 0, i1 = 0, previous, next; i0 < dataLength; ++i0) {
        if (previous = enterGroup[i0]) {
          if (i0 >= i1) i1 = i0 + 1;
          while (!(next = updateGroup[i1]) && ++i1 < dataLength) ;
          previous._next = next || null;
        }
      }
    }
    update = new Selection(update, parents);
    update._enter = enter;
    update._exit = exit;
    return update;
  }
  __name(data_default, "default");
  function arraylike(data) {
    return typeof data === "object" && "length" in data ? data : Array.from(data);
  }
  __name(arraylike, "arraylike");

  // node_modules/d3-selection/src/selection/exit.js
  function exit_default() {
    return new Selection(this._exit || this._groups.map(sparse_default), this._parents);
  }
  __name(exit_default, "default");

  // node_modules/d3-selection/src/selection/join.js
  function join_default(onenter, onupdate, onexit) {
    var enter = this.enter(), update = this, exit = this.exit();
    if (typeof onenter === "function") {
      enter = onenter(enter);
      if (enter) enter = enter.selection();
    } else {
      enter = enter.append(onenter + "");
    }
    if (onupdate != null) {
      update = onupdate(update);
      if (update) update = update.selection();
    }
    if (onexit == null) exit.remove();
    else onexit(exit);
    return enter && update ? enter.merge(update).order() : update;
  }
  __name(join_default, "default");

  // node_modules/d3-selection/src/selection/merge.js
  function merge_default(context) {
    var selection2 = context.selection ? context.selection() : context;
    for (var groups0 = this._groups, groups1 = selection2._groups, m0 = groups0.length, m1 = groups1.length, m = Math.min(m0, m1), merges = new Array(m0), j = 0; j < m; ++j) {
      for (var group0 = groups0[j], group1 = groups1[j], n = group0.length, merge = merges[j] = new Array(n), node, i = 0; i < n; ++i) {
        if (node = group0[i] || group1[i]) {
          merge[i] = node;
        }
      }
    }
    for (; j < m0; ++j) {
      merges[j] = groups0[j];
    }
    return new Selection(merges, this._parents);
  }
  __name(merge_default, "default");

  // node_modules/d3-selection/src/selection/order.js
  function order_default() {
    for (var groups = this._groups, j = -1, m = groups.length; ++j < m; ) {
      for (var group = groups[j], i = group.length - 1, next = group[i], node; --i >= 0; ) {
        if (node = group[i]) {
          if (next && node.compareDocumentPosition(next) ^ 4) next.parentNode.insertBefore(node, next);
          next = node;
        }
      }
    }
    return this;
  }
  __name(order_default, "default");

  // node_modules/d3-selection/src/selection/sort.js
  function sort_default2(compare) {
    if (!compare) compare = ascending;
    function compareNode(a, b) {
      return a && b ? compare(a.__data__, b.__data__) : !a - !b;
    }
    __name(compareNode, "compareNode");
    for (var groups = this._groups, m = groups.length, sortgroups = new Array(m), j = 0; j < m; ++j) {
      for (var group = groups[j], n = group.length, sortgroup = sortgroups[j] = new Array(n), node, i = 0; i < n; ++i) {
        if (node = group[i]) {
          sortgroup[i] = node;
        }
      }
      sortgroup.sort(compareNode);
    }
    return new Selection(sortgroups, this._parents).order();
  }
  __name(sort_default2, "default");
  function ascending(a, b) {
    return a < b ? -1 : a > b ? 1 : a >= b ? 0 : NaN;
  }
  __name(ascending, "ascending");

  // node_modules/d3-selection/src/selection/call.js
  function call_default() {
    var callback = arguments[0];
    arguments[0] = this;
    callback.apply(null, arguments);
    return this;
  }
  __name(call_default, "default");

  // node_modules/d3-selection/src/selection/nodes.js
  function nodes_default() {
    return Array.from(this);
  }
  __name(nodes_default, "default");

  // node_modules/d3-selection/src/selection/node.js
  function node_default() {
    for (var groups = this._groups, j = 0, m = groups.length; j < m; ++j) {
      for (var group = groups[j], i = 0, n = group.length; i < n; ++i) {
        var node = group[i];
        if (node) return node;
      }
    }
    return null;
  }
  __name(node_default, "default");

  // node_modules/d3-selection/src/selection/size.js
  function size_default() {
    let size = 0;
    for (const node of this) ++size;
    return size;
  }
  __name(size_default, "default");

  // node_modules/d3-selection/src/selection/empty.js
  function empty_default() {
    return !this.node();
  }
  __name(empty_default, "default");

  // node_modules/d3-selection/src/selection/each.js
  function each_default2(callback) {
    for (var groups = this._groups, j = 0, m = groups.length; j < m; ++j) {
      for (var group = groups[j], i = 0, n = group.length, node; i < n; ++i) {
        if (node = group[i]) callback.call(node, node.__data__, i, group);
      }
    }
    return this;
  }
  __name(each_default2, "default");

  // node_modules/d3-selection/src/selection/attr.js
  function attrRemove(name) {
    return function() {
      this.removeAttribute(name);
    };
  }
  __name(attrRemove, "attrRemove");
  function attrRemoveNS(fullname) {
    return function() {
      this.removeAttributeNS(fullname.space, fullname.local);
    };
  }
  __name(attrRemoveNS, "attrRemoveNS");
  function attrConstant(name, value) {
    return function() {
      this.setAttribute(name, value);
    };
  }
  __name(attrConstant, "attrConstant");
  function attrConstantNS(fullname, value) {
    return function() {
      this.setAttributeNS(fullname.space, fullname.local, value);
    };
  }
  __name(attrConstantNS, "attrConstantNS");
  function attrFunction(name, value) {
    return function() {
      var v = value.apply(this, arguments);
      if (v == null) this.removeAttribute(name);
      else this.setAttribute(name, v);
    };
  }
  __name(attrFunction, "attrFunction");
  function attrFunctionNS(fullname, value) {
    return function() {
      var v = value.apply(this, arguments);
      if (v == null) this.removeAttributeNS(fullname.space, fullname.local);
      else this.setAttributeNS(fullname.space, fullname.local, v);
    };
  }
  __name(attrFunctionNS, "attrFunctionNS");
  function attr_default(name, value) {
    var fullname = namespace_default(name);
    if (arguments.length < 2) {
      var node = this.node();
      return fullname.local ? node.getAttributeNS(fullname.space, fullname.local) : node.getAttribute(fullname);
    }
    return this.each((value == null ? fullname.local ? attrRemoveNS : attrRemove : typeof value === "function" ? fullname.local ? attrFunctionNS : attrFunction : fullname.local ? attrConstantNS : attrConstant)(fullname, value));
  }
  __name(attr_default, "default");

  // node_modules/d3-selection/src/window.js
  function window_default(node) {
    return node.ownerDocument && node.ownerDocument.defaultView || node.document && node || node.defaultView;
  }
  __name(window_default, "default");

  // node_modules/d3-selection/src/selection/style.js
  function styleRemove(name) {
    return function() {
      this.style.removeProperty(name);
    };
  }
  __name(styleRemove, "styleRemove");
  function styleConstant(name, value, priority) {
    return function() {
      this.style.setProperty(name, value, priority);
    };
  }
  __name(styleConstant, "styleConstant");
  function styleFunction(name, value, priority) {
    return function() {
      var v = value.apply(this, arguments);
      if (v == null) this.style.removeProperty(name);
      else this.style.setProperty(name, v, priority);
    };
  }
  __name(styleFunction, "styleFunction");
  function style_default(name, value, priority) {
    return arguments.length > 1 ? this.each((value == null ? styleRemove : typeof value === "function" ? styleFunction : styleConstant)(name, value, priority == null ? "" : priority)) : styleValue(this.node(), name);
  }
  __name(style_default, "default");
  function styleValue(node, name) {
    return node.style.getPropertyValue(name) || window_default(node).getComputedStyle(node, null).getPropertyValue(name);
  }
  __name(styleValue, "styleValue");

  // node_modules/d3-selection/src/selection/property.js
  function propertyRemove(name) {
    return function() {
      delete this[name];
    };
  }
  __name(propertyRemove, "propertyRemove");
  function propertyConstant(name, value) {
    return function() {
      this[name] = value;
    };
  }
  __name(propertyConstant, "propertyConstant");
  function propertyFunction(name, value) {
    return function() {
      var v = value.apply(this, arguments);
      if (v == null) delete this[name];
      else this[name] = v;
    };
  }
  __name(propertyFunction, "propertyFunction");
  function property_default(name, value) {
    return arguments.length > 1 ? this.each((value == null ? propertyRemove : typeof value === "function" ? propertyFunction : propertyConstant)(name, value)) : this.node()[name];
  }
  __name(property_default, "default");

  // node_modules/d3-selection/src/selection/classed.js
  function classArray(string) {
    return string.trim().split(/^|\s+/);
  }
  __name(classArray, "classArray");
  function classList(node) {
    return node.classList || new ClassList(node);
  }
  __name(classList, "classList");
  function ClassList(node) {
    this._node = node;
    this._names = classArray(node.getAttribute("class") || "");
  }
  __name(ClassList, "ClassList");
  ClassList.prototype = {
    add: /* @__PURE__ */ __name(function(name) {
      var i = this._names.indexOf(name);
      if (i < 0) {
        this._names.push(name);
        this._node.setAttribute("class", this._names.join(" "));
      }
    }, "add"),
    remove: /* @__PURE__ */ __name(function(name) {
      var i = this._names.indexOf(name);
      if (i >= 0) {
        this._names.splice(i, 1);
        this._node.setAttribute("class", this._names.join(" "));
      }
    }, "remove"),
    contains: /* @__PURE__ */ __name(function(name) {
      return this._names.indexOf(name) >= 0;
    }, "contains")
  };
  function classedAdd(node, names) {
    var list = classList(node), i = -1, n = names.length;
    while (++i < n) list.add(names[i]);
  }
  __name(classedAdd, "classedAdd");
  function classedRemove(node, names) {
    var list = classList(node), i = -1, n = names.length;
    while (++i < n) list.remove(names[i]);
  }
  __name(classedRemove, "classedRemove");
  function classedTrue(names) {
    return function() {
      classedAdd(this, names);
    };
  }
  __name(classedTrue, "classedTrue");
  function classedFalse(names) {
    return function() {
      classedRemove(this, names);
    };
  }
  __name(classedFalse, "classedFalse");
  function classedFunction(names, value) {
    return function() {
      (value.apply(this, arguments) ? classedAdd : classedRemove)(this, names);
    };
  }
  __name(classedFunction, "classedFunction");
  function classed_default(name, value) {
    var names = classArray(name + "");
    if (arguments.length < 2) {
      var list = classList(this.node()), i = -1, n = names.length;
      while (++i < n) if (!list.contains(names[i])) return false;
      return true;
    }
    return this.each((typeof value === "function" ? classedFunction : value ? classedTrue : classedFalse)(names, value));
  }
  __name(classed_default, "default");

  // node_modules/d3-selection/src/selection/text.js
  function textRemove() {
    this.textContent = "";
  }
  __name(textRemove, "textRemove");
  function textConstant(value) {
    return function() {
      this.textContent = value;
    };
  }
  __name(textConstant, "textConstant");
  function textFunction(value) {
    return function() {
      var v = value.apply(this, arguments);
      this.textContent = v == null ? "" : v;
    };
  }
  __name(textFunction, "textFunction");
  function text_default(value) {
    return arguments.length ? this.each(value == null ? textRemove : (typeof value === "function" ? textFunction : textConstant)(value)) : this.node().textContent;
  }
  __name(text_default, "default");

  // node_modules/d3-selection/src/selection/html.js
  function htmlRemove() {
    this.innerHTML = "";
  }
  __name(htmlRemove, "htmlRemove");
  function htmlConstant(value) {
    return function() {
      this.innerHTML = value;
    };
  }
  __name(htmlConstant, "htmlConstant");
  function htmlFunction(value) {
    return function() {
      var v = value.apply(this, arguments);
      this.innerHTML = v == null ? "" : v;
    };
  }
  __name(htmlFunction, "htmlFunction");
  function html_default(value) {
    return arguments.length ? this.each(value == null ? htmlRemove : (typeof value === "function" ? htmlFunction : htmlConstant)(value)) : this.node().innerHTML;
  }
  __name(html_default, "default");

  // node_modules/d3-selection/src/selection/raise.js
  function raise() {
    if (this.nextSibling) this.parentNode.appendChild(this);
  }
  __name(raise, "raise");
  function raise_default() {
    return this.each(raise);
  }
  __name(raise_default, "default");

  // node_modules/d3-selection/src/selection/lower.js
  function lower() {
    if (this.previousSibling) this.parentNode.insertBefore(this, this.parentNode.firstChild);
  }
  __name(lower, "lower");
  function lower_default() {
    return this.each(lower);
  }
  __name(lower_default, "default");

  // node_modules/d3-selection/src/selection/append.js
  function append_default(name) {
    var create3 = typeof name === "function" ? name : creator_default(name);
    return this.select(function() {
      return this.appendChild(create3.apply(this, arguments));
    });
  }
  __name(append_default, "default");

  // node_modules/d3-selection/src/selection/insert.js
  function constantNull() {
    return null;
  }
  __name(constantNull, "constantNull");
  function insert_default(name, before) {
    var create3 = typeof name === "function" ? name : creator_default(name), select = before == null ? constantNull : typeof before === "function" ? before : selector_default(before);
    return this.select(function() {
      return this.insertBefore(create3.apply(this, arguments), select.apply(this, arguments) || null);
    });
  }
  __name(insert_default, "default");

  // node_modules/d3-selection/src/selection/remove.js
  function remove() {
    var parent = this.parentNode;
    if (parent) parent.removeChild(this);
  }
  __name(remove, "remove");
  function remove_default() {
    return this.each(remove);
  }
  __name(remove_default, "default");

  // node_modules/d3-selection/src/selection/clone.js
  function selection_cloneShallow() {
    var clone = this.cloneNode(false), parent = this.parentNode;
    return parent ? parent.insertBefore(clone, this.nextSibling) : clone;
  }
  __name(selection_cloneShallow, "selection_cloneShallow");
  function selection_cloneDeep() {
    var clone = this.cloneNode(true), parent = this.parentNode;
    return parent ? parent.insertBefore(clone, this.nextSibling) : clone;
  }
  __name(selection_cloneDeep, "selection_cloneDeep");
  function clone_default(deep) {
    return this.select(deep ? selection_cloneDeep : selection_cloneShallow);
  }
  __name(clone_default, "default");

  // node_modules/d3-selection/src/selection/datum.js
  function datum_default(value) {
    return arguments.length ? this.property("__data__", value) : this.node().__data__;
  }
  __name(datum_default, "default");

  // node_modules/d3-selection/src/selection/on.js
  function contextListener(listener) {
    return function(event) {
      listener.call(this, event, this.__data__);
    };
  }
  __name(contextListener, "contextListener");
  function parseTypenames(typenames) {
    return typenames.trim().split(/^|\s+/).map(function(t) {
      var name = "", i = t.indexOf(".");
      if (i >= 0) name = t.slice(i + 1), t = t.slice(0, i);
      return { type: t, name };
    });
  }
  __name(parseTypenames, "parseTypenames");
  function onRemove(typename) {
    return function() {
      var on = this.__on;
      if (!on) return;
      for (var j = 0, i = -1, m = on.length, o; j < m; ++j) {
        if (o = on[j], (!typename.type || o.type === typename.type) && o.name === typename.name) {
          this.removeEventListener(o.type, o.listener, o.options);
        } else {
          on[++i] = o;
        }
      }
      if (++i) on.length = i;
      else delete this.__on;
    };
  }
  __name(onRemove, "onRemove");
  function onAdd(typename, value, options) {
    return function() {
      var on = this.__on, o, listener = contextListener(value);
      if (on) for (var j = 0, m = on.length; j < m; ++j) {
        if ((o = on[j]).type === typename.type && o.name === typename.name) {
          this.removeEventListener(o.type, o.listener, o.options);
          this.addEventListener(o.type, o.listener = listener, o.options = options);
          o.value = value;
          return;
        }
      }
      this.addEventListener(typename.type, listener, options);
      o = { type: typename.type, name: typename.name, value, listener, options };
      if (!on) this.__on = [o];
      else on.push(o);
    };
  }
  __name(onAdd, "onAdd");
  function on_default(typename, value, options) {
    var typenames = parseTypenames(typename + ""), i, n = typenames.length, t;
    if (arguments.length < 2) {
      var on = this.node().__on;
      if (on) for (var j = 0, m = on.length, o; j < m; ++j) {
        for (i = 0, o = on[j]; i < n; ++i) {
          if ((t = typenames[i]).type === o.type && t.name === o.name) {
            return o.value;
          }
        }
      }
      return;
    }
    on = value ? onAdd : onRemove;
    for (i = 0; i < n; ++i) this.each(on(typenames[i], value, options));
    return this;
  }
  __name(on_default, "default");

  // node_modules/d3-selection/src/selection/dispatch.js
  function dispatchEvent(node, type, params) {
    var window2 = window_default(node), event = window2.CustomEvent;
    if (typeof event === "function") {
      event = new event(type, params);
    } else {
      event = window2.document.createEvent("Event");
      if (params) event.initEvent(type, params.bubbles, params.cancelable), event.detail = params.detail;
      else event.initEvent(type, false, false);
    }
    node.dispatchEvent(event);
  }
  __name(dispatchEvent, "dispatchEvent");
  function dispatchConstant(type, params) {
    return function() {
      return dispatchEvent(this, type, params);
    };
  }
  __name(dispatchConstant, "dispatchConstant");
  function dispatchFunction(type, params) {
    return function() {
      return dispatchEvent(this, type, params.apply(this, arguments));
    };
  }
  __name(dispatchFunction, "dispatchFunction");
  function dispatch_default(type, params) {
    return this.each((typeof params === "function" ? dispatchFunction : dispatchConstant)(type, params));
  }
  __name(dispatch_default, "default");

  // node_modules/d3-selection/src/selection/iterator.js
  function* iterator_default2() {
    for (var groups = this._groups, j = 0, m = groups.length; j < m; ++j) {
      for (var group = groups[j], i = 0, n = group.length, node; i < n; ++i) {
        if (node = group[i]) yield node;
      }
    }
  }
  __name(iterator_default2, "default");

  // node_modules/d3-selection/src/selection/index.js
  var root = [null];
  function Selection(groups, parents) {
    this._groups = groups;
    this._parents = parents;
  }
  __name(Selection, "Selection");
  function selection() {
    return new Selection([[document.documentElement]], root);
  }
  __name(selection, "selection");
  function selection_selection() {
    return this;
  }
  __name(selection_selection, "selection_selection");
  Selection.prototype = selection.prototype = {
    constructor: Selection,
    select: select_default,
    selectAll: selectAll_default,
    selectChild: selectChild_default,
    selectChildren: selectChildren_default,
    filter: filter_default,
    data: data_default,
    enter: enter_default,
    exit: exit_default,
    join: join_default,
    merge: merge_default,
    selection: selection_selection,
    order: order_default,
    sort: sort_default2,
    call: call_default,
    nodes: nodes_default,
    node: node_default,
    size: size_default,
    empty: empty_default,
    each: each_default2,
    attr: attr_default,
    style: style_default,
    property: property_default,
    classed: classed_default,
    text: text_default,
    html: html_default,
    raise: raise_default,
    lower: lower_default,
    append: append_default,
    insert: insert_default,
    remove: remove_default,
    clone: clone_default,
    datum: datum_default,
    on: on_default,
    dispatch: dispatch_default,
    [Symbol.iterator]: iterator_default2
  };
  var selection_default = selection;

  // node_modules/d3-selection/src/select.js
  function select_default2(selector) {
    return typeof selector === "string" ? new Selection([[document.querySelector(selector)]], [document.documentElement]) : new Selection([[selector]], root);
  }
  __name(select_default2, "default");

  // node_modules/d3-selection/src/sourceEvent.js
  function sourceEvent_default(event) {
    let sourceEvent;
    while (sourceEvent = event.sourceEvent) event = sourceEvent;
    return event;
  }
  __name(sourceEvent_default, "default");

  // node_modules/d3-selection/src/pointer.js
  function pointer_default(event, node) {
    event = sourceEvent_default(event);
    if (node === void 0) node = event.currentTarget;
    if (node) {
      var svg = node.ownerSVGElement || node;
      if (svg.createSVGPoint) {
        var point = svg.createSVGPoint();
        point.x = event.clientX, point.y = event.clientY;
        point = point.matrixTransform(node.getScreenCTM().inverse());
        return [point.x, point.y];
      }
      if (node.getBoundingClientRect) {
        var rect = node.getBoundingClientRect();
        return [event.clientX - rect.left - node.clientLeft, event.clientY - rect.top - node.clientTop];
      }
    }
    return [event.pageX, event.pageY];
  }
  __name(pointer_default, "default");

  // node_modules/d3-selection/src/selectAll.js
  function selectAll_default2(selector) {
    return typeof selector === "string" ? new Selection([document.querySelectorAll(selector)], [document.documentElement]) : new Selection([array(selector)], root);
  }
  __name(selectAll_default2, "default");

  // node_modules/d3-dispatch/src/dispatch.js
  var noop = { value: /* @__PURE__ */ __name(() => {
  }, "value") };
  function dispatch() {
    for (var i = 0, n = arguments.length, _ = {}, t; i < n; ++i) {
      if (!(t = arguments[i] + "") || t in _ || /[\s.]/.test(t)) throw new Error("illegal type: " + t);
      _[t] = [];
    }
    return new Dispatch(_);
  }
  __name(dispatch, "dispatch");
  function Dispatch(_) {
    this._ = _;
  }
  __name(Dispatch, "Dispatch");
  function parseTypenames2(typenames, types) {
    return typenames.trim().split(/^|\s+/).map(function(t) {
      var name = "", i = t.indexOf(".");
      if (i >= 0) name = t.slice(i + 1), t = t.slice(0, i);
      if (t && !types.hasOwnProperty(t)) throw new Error("unknown type: " + t);
      return { type: t, name };
    });
  }
  __name(parseTypenames2, "parseTypenames");
  Dispatch.prototype = dispatch.prototype = {
    constructor: Dispatch,
    on: /* @__PURE__ */ __name(function(typename, callback) {
      var _ = this._, T = parseTypenames2(typename + "", _), t, i = -1, n = T.length;
      if (arguments.length < 2) {
        while (++i < n) if ((t = (typename = T[i]).type) && (t = get(_[t], typename.name))) return t;
        return;
      }
      if (callback != null && typeof callback !== "function") throw new Error("invalid callback: " + callback);
      while (++i < n) {
        if (t = (typename = T[i]).type) _[t] = set(_[t], typename.name, callback);
        else if (callback == null) for (t in _) _[t] = set(_[t], typename.name, null);
      }
      return this;
    }, "on"),
    copy: /* @__PURE__ */ __name(function() {
      var copy = {}, _ = this._;
      for (var t in _) copy[t] = _[t].slice();
      return new Dispatch(copy);
    }, "copy"),
    call: /* @__PURE__ */ __name(function(type, that) {
      if ((n = arguments.length - 2) > 0) for (var args = new Array(n), i = 0, n, t; i < n; ++i) args[i] = arguments[i + 2];
      if (!this._.hasOwnProperty(type)) throw new Error("unknown type: " + type);
      for (t = this._[type], i = 0, n = t.length; i < n; ++i) t[i].value.apply(that, args);
    }, "call"),
    apply: /* @__PURE__ */ __name(function(type, that, args) {
      if (!this._.hasOwnProperty(type)) throw new Error("unknown type: " + type);
      for (var t = this._[type], i = 0, n = t.length; i < n; ++i) t[i].value.apply(that, args);
    }, "apply")
  };
  function get(type, name) {
    for (var i = 0, n = type.length, c; i < n; ++i) {
      if ((c = type[i]).name === name) {
        return c.value;
      }
    }
  }
  __name(get, "get");
  function set(type, name, callback) {
    for (var i = 0, n = type.length; i < n; ++i) {
      if (type[i].name === name) {
        type[i] = noop, type = type.slice(0, i).concat(type.slice(i + 1));
        break;
      }
    }
    if (callback != null) type.push({ name, value: callback });
    return type;
  }
  __name(set, "set");
  var dispatch_default2 = dispatch;

  // node_modules/d3-drag/src/noevent.js
  var nonpassivecapture = { capture: true, passive: false };
  function noevent_default(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
  __name(noevent_default, "default");

  // node_modules/d3-drag/src/nodrag.js
  function nodrag_default(view) {
    var root2 = view.document.documentElement, selection2 = select_default2(view).on("dragstart.drag", noevent_default, nonpassivecapture);
    if ("onselectstart" in root2) {
      selection2.on("selectstart.drag", noevent_default, nonpassivecapture);
    } else {
      root2.__noselect = root2.style.MozUserSelect;
      root2.style.MozUserSelect = "none";
    }
  }
  __name(nodrag_default, "default");
  function yesdrag(view, noclick) {
    var root2 = view.document.documentElement, selection2 = select_default2(view).on("dragstart.drag", null);
    if (noclick) {
      selection2.on("click.drag", noevent_default, nonpassivecapture);
      setTimeout(function() {
        selection2.on("click.drag", null);
      }, 0);
    }
    if ("onselectstart" in root2) {
      selection2.on("selectstart.drag", null);
    } else {
      root2.style.MozUserSelect = root2.__noselect;
      delete root2.__noselect;
    }
  }
  __name(yesdrag, "yesdrag");

  // node_modules/d3-color/src/define.js
  function define_default(constructor, factory, prototype) {
    constructor.prototype = factory.prototype = prototype;
    prototype.constructor = constructor;
  }
  __name(define_default, "default");
  function extend(parent, definition) {
    var prototype = Object.create(parent.prototype);
    for (var key in definition) prototype[key] = definition[key];
    return prototype;
  }
  __name(extend, "extend");

  // node_modules/d3-color/src/color.js
  function Color() {
  }
  __name(Color, "Color");
  var darker = 0.7;
  var brighter = 1 / darker;
  var reI = "\\s*([+-]?\\d+)\\s*";
  var reN = "\\s*([+-]?(?:\\d*\\.)?\\d+(?:[eE][+-]?\\d+)?)\\s*";
  var reP = "\\s*([+-]?(?:\\d*\\.)?\\d+(?:[eE][+-]?\\d+)?)%\\s*";
  var reHex = /^#([0-9a-f]{3,8})$/;
  var reRgbInteger = new RegExp(`^rgb\\(${reI},${reI},${reI}\\)$`);
  var reRgbPercent = new RegExp(`^rgb\\(${reP},${reP},${reP}\\)$`);
  var reRgbaInteger = new RegExp(`^rgba\\(${reI},${reI},${reI},${reN}\\)$`);
  var reRgbaPercent = new RegExp(`^rgba\\(${reP},${reP},${reP},${reN}\\)$`);
  var reHslPercent = new RegExp(`^hsl\\(${reN},${reP},${reP}\\)$`);
  var reHslaPercent = new RegExp(`^hsla\\(${reN},${reP},${reP},${reN}\\)$`);
  var named = {
    aliceblue: 15792383,
    antiquewhite: 16444375,
    aqua: 65535,
    aquamarine: 8388564,
    azure: 15794175,
    beige: 16119260,
    bisque: 16770244,
    black: 0,
    blanchedalmond: 16772045,
    blue: 255,
    blueviolet: 9055202,
    brown: 10824234,
    burlywood: 14596231,
    cadetblue: 6266528,
    chartreuse: 8388352,
    chocolate: 13789470,
    coral: 16744272,
    cornflowerblue: 6591981,
    cornsilk: 16775388,
    crimson: 14423100,
    cyan: 65535,
    darkblue: 139,
    darkcyan: 35723,
    darkgoldenrod: 12092939,
    darkgray: 11119017,
    darkgreen: 25600,
    darkgrey: 11119017,
    darkkhaki: 12433259,
    darkmagenta: 9109643,
    darkolivegreen: 5597999,
    darkorange: 16747520,
    darkorchid: 10040012,
    darkred: 9109504,
    darksalmon: 15308410,
    darkseagreen: 9419919,
    darkslateblue: 4734347,
    darkslategray: 3100495,
    darkslategrey: 3100495,
    darkturquoise: 52945,
    darkviolet: 9699539,
    deeppink: 16716947,
    deepskyblue: 49151,
    dimgray: 6908265,
    dimgrey: 6908265,
    dodgerblue: 2003199,
    firebrick: 11674146,
    floralwhite: 16775920,
    forestgreen: 2263842,
    fuchsia: 16711935,
    gainsboro: 14474460,
    ghostwhite: 16316671,
    gold: 16766720,
    goldenrod: 14329120,
    gray: 8421504,
    green: 32768,
    greenyellow: 11403055,
    grey: 8421504,
    honeydew: 15794160,
    hotpink: 16738740,
    indianred: 13458524,
    indigo: 4915330,
    ivory: 16777200,
    khaki: 15787660,
    lavender: 15132410,
    lavenderblush: 16773365,
    lawngreen: 8190976,
    lemonchiffon: 16775885,
    lightblue: 11393254,
    lightcoral: 15761536,
    lightcyan: 14745599,
    lightgoldenrodyellow: 16448210,
    lightgray: 13882323,
    lightgreen: 9498256,
    lightgrey: 13882323,
    lightpink: 16758465,
    lightsalmon: 16752762,
    lightseagreen: 2142890,
    lightskyblue: 8900346,
    lightslategray: 7833753,
    lightslategrey: 7833753,
    lightsteelblue: 11584734,
    lightyellow: 16777184,
    lime: 65280,
    limegreen: 3329330,
    linen: 16445670,
    magenta: 16711935,
    maroon: 8388608,
    mediumaquamarine: 6737322,
    mediumblue: 205,
    mediumorchid: 12211667,
    mediumpurple: 9662683,
    mediumseagreen: 3978097,
    mediumslateblue: 8087790,
    mediumspringgreen: 64154,
    mediumturquoise: 4772300,
    mediumvioletred: 13047173,
    midnightblue: 1644912,
    mintcream: 16121850,
    mistyrose: 16770273,
    moccasin: 16770229,
    navajowhite: 16768685,
    navy: 128,
    oldlace: 16643558,
    olive: 8421376,
    olivedrab: 7048739,
    orange: 16753920,
    orangered: 16729344,
    orchid: 14315734,
    palegoldenrod: 15657130,
    palegreen: 10025880,
    paleturquoise: 11529966,
    palevioletred: 14381203,
    papayawhip: 16773077,
    peachpuff: 16767673,
    peru: 13468991,
    pink: 16761035,
    plum: 14524637,
    powderblue: 11591910,
    purple: 8388736,
    rebeccapurple: 6697881,
    red: 16711680,
    rosybrown: 12357519,
    royalblue: 4286945,
    saddlebrown: 9127187,
    salmon: 16416882,
    sandybrown: 16032864,
    seagreen: 3050327,
    seashell: 16774638,
    sienna: 10506797,
    silver: 12632256,
    skyblue: 8900331,
    slateblue: 6970061,
    slategray: 7372944,
    slategrey: 7372944,
    snow: 16775930,
    springgreen: 65407,
    steelblue: 4620980,
    tan: 13808780,
    teal: 32896,
    thistle: 14204888,
    tomato: 16737095,
    turquoise: 4251856,
    violet: 15631086,
    wheat: 16113331,
    white: 16777215,
    whitesmoke: 16119285,
    yellow: 16776960,
    yellowgreen: 10145074
  };
  define_default(Color, color, {
    copy(channels) {
      return Object.assign(new this.constructor(), this, channels);
    },
    displayable() {
      return this.rgb().displayable();
    },
    hex: color_formatHex,
    // Deprecated! Use color.formatHex.
    formatHex: color_formatHex,
    formatHex8: color_formatHex8,
    formatHsl: color_formatHsl,
    formatRgb: color_formatRgb,
    toString: color_formatRgb
  });
  function color_formatHex() {
    return this.rgb().formatHex();
  }
  __name(color_formatHex, "color_formatHex");
  function color_formatHex8() {
    return this.rgb().formatHex8();
  }
  __name(color_formatHex8, "color_formatHex8");
  function color_formatHsl() {
    return hslConvert(this).formatHsl();
  }
  __name(color_formatHsl, "color_formatHsl");
  function color_formatRgb() {
    return this.rgb().formatRgb();
  }
  __name(color_formatRgb, "color_formatRgb");
  function color(format) {
    var m, l;
    format = (format + "").trim().toLowerCase();
    return (m = reHex.exec(format)) ? (l = m[1].length, m = parseInt(m[1], 16), l === 6 ? rgbn(m) : l === 3 ? new Rgb(m >> 8 & 15 | m >> 4 & 240, m >> 4 & 15 | m & 240, (m & 15) << 4 | m & 15, 1) : l === 8 ? rgba(m >> 24 & 255, m >> 16 & 255, m >> 8 & 255, (m & 255) / 255) : l === 4 ? rgba(m >> 12 & 15 | m >> 8 & 240, m >> 8 & 15 | m >> 4 & 240, m >> 4 & 15 | m & 240, ((m & 15) << 4 | m & 15) / 255) : null) : (m = reRgbInteger.exec(format)) ? new Rgb(m[1], m[2], m[3], 1) : (m = reRgbPercent.exec(format)) ? new Rgb(m[1] * 255 / 100, m[2] * 255 / 100, m[3] * 255 / 100, 1) : (m = reRgbaInteger.exec(format)) ? rgba(m[1], m[2], m[3], m[4]) : (m = reRgbaPercent.exec(format)) ? rgba(m[1] * 255 / 100, m[2] * 255 / 100, m[3] * 255 / 100, m[4]) : (m = reHslPercent.exec(format)) ? hsla(m[1], m[2] / 100, m[3] / 100, 1) : (m = reHslaPercent.exec(format)) ? hsla(m[1], m[2] / 100, m[3] / 100, m[4]) : named.hasOwnProperty(format) ? rgbn(named[format]) : format === "transparent" ? new Rgb(NaN, NaN, NaN, 0) : null;
  }
  __name(color, "color");
  function rgbn(n) {
    return new Rgb(n >> 16 & 255, n >> 8 & 255, n & 255, 1);
  }
  __name(rgbn, "rgbn");
  function rgba(r, g, b, a) {
    if (a <= 0) r = g = b = NaN;
    return new Rgb(r, g, b, a);
  }
  __name(rgba, "rgba");
  function rgbConvert(o) {
    if (!(o instanceof Color)) o = color(o);
    if (!o) return new Rgb();
    o = o.rgb();
    return new Rgb(o.r, o.g, o.b, o.opacity);
  }
  __name(rgbConvert, "rgbConvert");
  function rgb(r, g, b, opacity) {
    return arguments.length === 1 ? rgbConvert(r) : new Rgb(r, g, b, opacity == null ? 1 : opacity);
  }
  __name(rgb, "rgb");
  function Rgb(r, g, b, opacity) {
    this.r = +r;
    this.g = +g;
    this.b = +b;
    this.opacity = +opacity;
  }
  __name(Rgb, "Rgb");
  define_default(Rgb, rgb, extend(Color, {
    brighter(k) {
      k = k == null ? brighter : Math.pow(brighter, k);
      return new Rgb(this.r * k, this.g * k, this.b * k, this.opacity);
    },
    darker(k) {
      k = k == null ? darker : Math.pow(darker, k);
      return new Rgb(this.r * k, this.g * k, this.b * k, this.opacity);
    },
    rgb() {
      return this;
    },
    clamp() {
      return new Rgb(clampi(this.r), clampi(this.g), clampi(this.b), clampa(this.opacity));
    },
    displayable() {
      return -0.5 <= this.r && this.r < 255.5 && (-0.5 <= this.g && this.g < 255.5) && (-0.5 <= this.b && this.b < 255.5) && (0 <= this.opacity && this.opacity <= 1);
    },
    hex: rgb_formatHex,
    // Deprecated! Use color.formatHex.
    formatHex: rgb_formatHex,
    formatHex8: rgb_formatHex8,
    formatRgb: rgb_formatRgb,
    toString: rgb_formatRgb
  }));
  function rgb_formatHex() {
    return `#${hex(this.r)}${hex(this.g)}${hex(this.b)}`;
  }
  __name(rgb_formatHex, "rgb_formatHex");
  function rgb_formatHex8() {
    return `#${hex(this.r)}${hex(this.g)}${hex(this.b)}${hex((isNaN(this.opacity) ? 1 : this.opacity) * 255)}`;
  }
  __name(rgb_formatHex8, "rgb_formatHex8");
  function rgb_formatRgb() {
    const a = clampa(this.opacity);
    return `${a === 1 ? "rgb(" : "rgba("}${clampi(this.r)}, ${clampi(this.g)}, ${clampi(this.b)}${a === 1 ? ")" : `, ${a})`}`;
  }
  __name(rgb_formatRgb, "rgb_formatRgb");
  function clampa(opacity) {
    return isNaN(opacity) ? 1 : Math.max(0, Math.min(1, opacity));
  }
  __name(clampa, "clampa");
  function clampi(value) {
    return Math.max(0, Math.min(255, Math.round(value) || 0));
  }
  __name(clampi, "clampi");
  function hex(value) {
    value = clampi(value);
    return (value < 16 ? "0" : "") + value.toString(16);
  }
  __name(hex, "hex");
  function hsla(h, s, l, a) {
    if (a <= 0) h = s = l = NaN;
    else if (l <= 0 || l >= 1) h = s = NaN;
    else if (s <= 0) h = NaN;
    return new Hsl(h, s, l, a);
  }
  __name(hsla, "hsla");
  function hslConvert(o) {
    if (o instanceof Hsl) return new Hsl(o.h, o.s, o.l, o.opacity);
    if (!(o instanceof Color)) o = color(o);
    if (!o) return new Hsl();
    if (o instanceof Hsl) return o;
    o = o.rgb();
    var r = o.r / 255, g = o.g / 255, b = o.b / 255, min = Math.min(r, g, b), max = Math.max(r, g, b), h = NaN, s = max - min, l = (max + min) / 2;
    if (s) {
      if (r === max) h = (g - b) / s + (g < b) * 6;
      else if (g === max) h = (b - r) / s + 2;
      else h = (r - g) / s + 4;
      s /= l < 0.5 ? max + min : 2 - max - min;
      h *= 60;
    } else {
      s = l > 0 && l < 1 ? 0 : h;
    }
    return new Hsl(h, s, l, o.opacity);
  }
  __name(hslConvert, "hslConvert");
  function hsl(h, s, l, opacity) {
    return arguments.length === 1 ? hslConvert(h) : new Hsl(h, s, l, opacity == null ? 1 : opacity);
  }
  __name(hsl, "hsl");
  function Hsl(h, s, l, opacity) {
    this.h = +h;
    this.s = +s;
    this.l = +l;
    this.opacity = +opacity;
  }
  __name(Hsl, "Hsl");
  define_default(Hsl, hsl, extend(Color, {
    brighter(k) {
      k = k == null ? brighter : Math.pow(brighter, k);
      return new Hsl(this.h, this.s, this.l * k, this.opacity);
    },
    darker(k) {
      k = k == null ? darker : Math.pow(darker, k);
      return new Hsl(this.h, this.s, this.l * k, this.opacity);
    },
    rgb() {
      var h = this.h % 360 + (this.h < 0) * 360, s = isNaN(h) || isNaN(this.s) ? 0 : this.s, l = this.l, m2 = l + (l < 0.5 ? l : 1 - l) * s, m1 = 2 * l - m2;
      return new Rgb(
        hsl2rgb(h >= 240 ? h - 240 : h + 120, m1, m2),
        hsl2rgb(h, m1, m2),
        hsl2rgb(h < 120 ? h + 240 : h - 120, m1, m2),
        this.opacity
      );
    },
    clamp() {
      return new Hsl(clamph(this.h), clampt(this.s), clampt(this.l), clampa(this.opacity));
    },
    displayable() {
      return (0 <= this.s && this.s <= 1 || isNaN(this.s)) && (0 <= this.l && this.l <= 1) && (0 <= this.opacity && this.opacity <= 1);
    },
    formatHsl() {
      const a = clampa(this.opacity);
      return `${a === 1 ? "hsl(" : "hsla("}${clamph(this.h)}, ${clampt(this.s) * 100}%, ${clampt(this.l) * 100}%${a === 1 ? ")" : `, ${a})`}`;
    }
  }));
  function clamph(value) {
    value = (value || 0) % 360;
    return value < 0 ? value + 360 : value;
  }
  __name(clamph, "clamph");
  function clampt(value) {
    return Math.max(0, Math.min(1, value || 0));
  }
  __name(clampt, "clampt");
  function hsl2rgb(h, m1, m2) {
    return (h < 60 ? m1 + (m2 - m1) * h / 60 : h < 180 ? m2 : h < 240 ? m1 + (m2 - m1) * (240 - h) / 60 : m1) * 255;
  }
  __name(hsl2rgb, "hsl2rgb");

  // node_modules/d3-interpolate/src/basis.js
  function basis(t1, v0, v1, v2, v3) {
    var t2 = t1 * t1, t3 = t2 * t1;
    return ((1 - 3 * t1 + 3 * t2 - t3) * v0 + (4 - 6 * t2 + 3 * t3) * v1 + (1 + 3 * t1 + 3 * t2 - 3 * t3) * v2 + t3 * v3) / 6;
  }
  __name(basis, "basis");
  function basis_default(values) {
    var n = values.length - 1;
    return function(t) {
      var i = t <= 0 ? t = 0 : t >= 1 ? (t = 1, n - 1) : Math.floor(t * n), v1 = values[i], v2 = values[i + 1], v0 = i > 0 ? values[i - 1] : 2 * v1 - v2, v3 = i < n - 1 ? values[i + 2] : 2 * v2 - v1;
      return basis((t - i / n) * n, v0, v1, v2, v3);
    };
  }
  __name(basis_default, "default");

  // node_modules/d3-interpolate/src/basisClosed.js
  function basisClosed_default(values) {
    var n = values.length;
    return function(t) {
      var i = Math.floor(((t %= 1) < 0 ? ++t : t) * n), v0 = values[(i + n - 1) % n], v1 = values[i % n], v2 = values[(i + 1) % n], v3 = values[(i + 2) % n];
      return basis((t - i / n) * n, v0, v1, v2, v3);
    };
  }
  __name(basisClosed_default, "default");

  // node_modules/d3-interpolate/src/constant.js
  var constant_default3 = /* @__PURE__ */ __name((x) => () => x, "default");

  // node_modules/d3-interpolate/src/color.js
  function linear(a, d) {
    return function(t) {
      return a + t * d;
    };
  }
  __name(linear, "linear");
  function exponential(a, b, y) {
    return a = Math.pow(a, y), b = Math.pow(b, y) - a, y = 1 / y, function(t) {
      return Math.pow(a + t * b, y);
    };
  }
  __name(exponential, "exponential");
  function gamma(y) {
    return (y = +y) === 1 ? nogamma : function(a, b) {
      return b - a ? exponential(a, b, y) : constant_default3(isNaN(a) ? b : a);
    };
  }
  __name(gamma, "gamma");
  function nogamma(a, b) {
    var d = b - a;
    return d ? linear(a, d) : constant_default3(isNaN(a) ? b : a);
  }
  __name(nogamma, "nogamma");

  // node_modules/d3-interpolate/src/rgb.js
  var rgb_default = (/* @__PURE__ */ __name(function rgbGamma(y) {
    var color2 = gamma(y);
    function rgb2(start2, end) {
      var r = color2((start2 = rgb(start2)).r, (end = rgb(end)).r), g = color2(start2.g, end.g), b = color2(start2.b, end.b), opacity = nogamma(start2.opacity, end.opacity);
      return function(t) {
        start2.r = r(t);
        start2.g = g(t);
        start2.b = b(t);
        start2.opacity = opacity(t);
        return start2 + "";
      };
    }
    __name(rgb2, "rgb");
    rgb2.gamma = rgbGamma;
    return rgb2;
  }, "rgbGamma"))(1);
  function rgbSpline(spline) {
    return function(colors) {
      var n = colors.length, r = new Array(n), g = new Array(n), b = new Array(n), i, color2;
      for (i = 0; i < n; ++i) {
        color2 = rgb(colors[i]);
        r[i] = color2.r || 0;
        g[i] = color2.g || 0;
        b[i] = color2.b || 0;
      }
      r = spline(r);
      g = spline(g);
      b = spline(b);
      color2.opacity = 1;
      return function(t) {
        color2.r = r(t);
        color2.g = g(t);
        color2.b = b(t);
        return color2 + "";
      };
    };
  }
  __name(rgbSpline, "rgbSpline");
  var rgbBasis = rgbSpline(basis_default);
  var rgbBasisClosed = rgbSpline(basisClosed_default);

  // node_modules/d3-interpolate/src/number.js
  function number_default(a, b) {
    return a = +a, b = +b, function(t) {
      return a * (1 - t) + b * t;
    };
  }
  __name(number_default, "default");

  // node_modules/d3-interpolate/src/string.js
  var reA = /[-+]?(?:\d+\.?\d*|\.?\d+)(?:[eE][-+]?\d+)?/g;
  var reB = new RegExp(reA.source, "g");
  function zero(b) {
    return function() {
      return b;
    };
  }
  __name(zero, "zero");
  function one(b) {
    return function(t) {
      return b(t) + "";
    };
  }
  __name(one, "one");
  function string_default(a, b) {
    var bi = reA.lastIndex = reB.lastIndex = 0, am, bm, bs, i = -1, s = [], q = [];
    a = a + "", b = b + "";
    while ((am = reA.exec(a)) && (bm = reB.exec(b))) {
      if ((bs = bm.index) > bi) {
        bs = b.slice(bi, bs);
        if (s[i]) s[i] += bs;
        else s[++i] = bs;
      }
      if ((am = am[0]) === (bm = bm[0])) {
        if (s[i]) s[i] += bm;
        else s[++i] = bm;
      } else {
        s[++i] = null;
        q.push({ i, x: number_default(am, bm) });
      }
      bi = reB.lastIndex;
    }
    if (bi < b.length) {
      bs = b.slice(bi);
      if (s[i]) s[i] += bs;
      else s[++i] = bs;
    }
    return s.length < 2 ? q[0] ? one(q[0].x) : zero(b) : (b = q.length, function(t) {
      for (var i2 = 0, o; i2 < b; ++i2) s[(o = q[i2]).i] = o.x(t);
      return s.join("");
    });
  }
  __name(string_default, "default");

  // node_modules/d3-interpolate/src/transform/decompose.js
  var degrees = 180 / Math.PI;
  var identity = {
    translateX: 0,
    translateY: 0,
    rotate: 0,
    skewX: 0,
    scaleX: 1,
    scaleY: 1
  };
  function decompose_default(a, b, c, d, e, f) {
    var scaleX, scaleY, skewX;
    if (scaleX = Math.sqrt(a * a + b * b)) a /= scaleX, b /= scaleX;
    if (skewX = a * c + b * d) c -= a * skewX, d -= b * skewX;
    if (scaleY = Math.sqrt(c * c + d * d)) c /= scaleY, d /= scaleY, skewX /= scaleY;
    if (a * d < b * c) a = -a, b = -b, skewX = -skewX, scaleX = -scaleX;
    return {
      translateX: e,
      translateY: f,
      rotate: Math.atan2(b, a) * degrees,
      skewX: Math.atan(skewX) * degrees,
      scaleX,
      scaleY
    };
  }
  __name(decompose_default, "default");

  // node_modules/d3-interpolate/src/transform/parse.js
  var svgNode;
  function parseCss(value) {
    const m = new (typeof DOMMatrix === "function" ? DOMMatrix : WebKitCSSMatrix)(value + "");
    return m.isIdentity ? identity : decompose_default(m.a, m.b, m.c, m.d, m.e, m.f);
  }
  __name(parseCss, "parseCss");
  function parseSvg(value) {
    if (value == null) return identity;
    if (!svgNode) svgNode = document.createElementNS("http://www.w3.org/2000/svg", "g");
    svgNode.setAttribute("transform", value);
    if (!(value = svgNode.transform.baseVal.consolidate())) return identity;
    value = value.matrix;
    return decompose_default(value.a, value.b, value.c, value.d, value.e, value.f);
  }
  __name(parseSvg, "parseSvg");

  // node_modules/d3-interpolate/src/transform/index.js
  function interpolateTransform(parse, pxComma, pxParen, degParen) {
    function pop(s) {
      return s.length ? s.pop() + " " : "";
    }
    __name(pop, "pop");
    function translate(xa, ya, xb, yb, s, q) {
      if (xa !== xb || ya !== yb) {
        var i = s.push("translate(", null, pxComma, null, pxParen);
        q.push({ i: i - 4, x: number_default(xa, xb) }, { i: i - 2, x: number_default(ya, yb) });
      } else if (xb || yb) {
        s.push("translate(" + xb + pxComma + yb + pxParen);
      }
    }
    __name(translate, "translate");
    function rotate(a, b, s, q) {
      if (a !== b) {
        if (a - b > 180) b += 360;
        else if (b - a > 180) a += 360;
        q.push({ i: s.push(pop(s) + "rotate(", null, degParen) - 2, x: number_default(a, b) });
      } else if (b) {
        s.push(pop(s) + "rotate(" + b + degParen);
      }
    }
    __name(rotate, "rotate");
    function skewX(a, b, s, q) {
      if (a !== b) {
        q.push({ i: s.push(pop(s) + "skewX(", null, degParen) - 2, x: number_default(a, b) });
      } else if (b) {
        s.push(pop(s) + "skewX(" + b + degParen);
      }
    }
    __name(skewX, "skewX");
    function scale(xa, ya, xb, yb, s, q) {
      if (xa !== xb || ya !== yb) {
        var i = s.push(pop(s) + "scale(", null, ",", null, ")");
        q.push({ i: i - 4, x: number_default(xa, xb) }, { i: i - 2, x: number_default(ya, yb) });
      } else if (xb !== 1 || yb !== 1) {
        s.push(pop(s) + "scale(" + xb + "," + yb + ")");
      }
    }
    __name(scale, "scale");
    return function(a, b) {
      var s = [], q = [];
      a = parse(a), b = parse(b);
      translate(a.translateX, a.translateY, b.translateX, b.translateY, s, q);
      rotate(a.rotate, b.rotate, s, q);
      skewX(a.skewX, b.skewX, s, q);
      scale(a.scaleX, a.scaleY, b.scaleX, b.scaleY, s, q);
      a = b = null;
      return function(t) {
        var i = -1, n = q.length, o;
        while (++i < n) s[(o = q[i]).i] = o.x(t);
        return s.join("");
      };
    };
  }
  __name(interpolateTransform, "interpolateTransform");
  var interpolateTransformCss = interpolateTransform(parseCss, "px, ", "px)", "deg)");
  var interpolateTransformSvg = interpolateTransform(parseSvg, ", ", ")", ")");

  // node_modules/d3-interpolate/src/zoom.js
  var epsilon2 = 1e-12;
  function cosh(x) {
    return ((x = Math.exp(x)) + 1 / x) / 2;
  }
  __name(cosh, "cosh");
  function sinh(x) {
    return ((x = Math.exp(x)) - 1 / x) / 2;
  }
  __name(sinh, "sinh");
  function tanh(x) {
    return ((x = Math.exp(2 * x)) - 1) / (x + 1);
  }
  __name(tanh, "tanh");
  var zoom_default = (/* @__PURE__ */ __name(function zoomRho(rho, rho2, rho4) {
    function zoom(p0, p1) {
      var ux0 = p0[0], uy0 = p0[1], w0 = p0[2], ux1 = p1[0], uy1 = p1[1], w1 = p1[2], dx = ux1 - ux0, dy = uy1 - uy0, d2 = dx * dx + dy * dy, i, S;
      if (d2 < epsilon2) {
        S = Math.log(w1 / w0) / rho;
        i = /* @__PURE__ */ __name(function(t) {
          return [
            ux0 + t * dx,
            uy0 + t * dy,
            w0 * Math.exp(rho * t * S)
          ];
        }, "i");
      } else {
        var d1 = Math.sqrt(d2), b0 = (w1 * w1 - w0 * w0 + rho4 * d2) / (2 * w0 * rho2 * d1), b1 = (w1 * w1 - w0 * w0 - rho4 * d2) / (2 * w1 * rho2 * d1), r0 = Math.log(Math.sqrt(b0 * b0 + 1) - b0), r1 = Math.log(Math.sqrt(b1 * b1 + 1) - b1);
        S = (r1 - r0) / rho;
        i = /* @__PURE__ */ __name(function(t) {
          var s = t * S, coshr0 = cosh(r0), u = w0 / (rho2 * d1) * (coshr0 * tanh(rho * s + r0) - sinh(r0));
          return [
            ux0 + u * dx,
            uy0 + u * dy,
            w0 * coshr0 / cosh(rho * s + r0)
          ];
        }, "i");
      }
      i.duration = S * 1e3 * rho / Math.SQRT2;
      return i;
    }
    __name(zoom, "zoom");
    zoom.rho = function(_) {
      var _1 = Math.max(1e-3, +_), _2 = _1 * _1, _4 = _2 * _2;
      return zoomRho(_1, _2, _4);
    };
    return zoom;
  }, "zoomRho"))(Math.SQRT2, 2, 4);

  // node_modules/d3-timer/src/timer.js
  var frame = 0;
  var timeout = 0;
  var interval = 0;
  var pokeDelay = 1e3;
  var taskHead;
  var taskTail;
  var clockLast = 0;
  var clockNow = 0;
  var clockSkew = 0;
  var clock = typeof performance === "object" && performance.now ? performance : Date;
  var setFrame = typeof window === "object" && window.requestAnimationFrame ? window.requestAnimationFrame.bind(window) : function(f) {
    setTimeout(f, 17);
  };
  function now() {
    return clockNow || (setFrame(clearNow), clockNow = clock.now() + clockSkew);
  }
  __name(now, "now");
  function clearNow() {
    clockNow = 0;
  }
  __name(clearNow, "clearNow");
  function Timer() {
    this._call = this._time = this._next = null;
  }
  __name(Timer, "Timer");
  Timer.prototype = timer.prototype = {
    constructor: Timer,
    restart: /* @__PURE__ */ __name(function(callback, delay, time) {
      if (typeof callback !== "function") throw new TypeError("callback is not a function");
      time = (time == null ? now() : +time) + (delay == null ? 0 : +delay);
      if (!this._next && taskTail !== this) {
        if (taskTail) taskTail._next = this;
        else taskHead = this;
        taskTail = this;
      }
      this._call = callback;
      this._time = time;
      sleep();
    }, "restart"),
    stop: /* @__PURE__ */ __name(function() {
      if (this._call) {
        this._call = null;
        this._time = Infinity;
        sleep();
      }
    }, "stop")
  };
  function timer(callback, delay, time) {
    var t = new Timer();
    t.restart(callback, delay, time);
    return t;
  }
  __name(timer, "timer");
  function timerFlush() {
    now();
    ++frame;
    var t = taskHead, e;
    while (t) {
      if ((e = clockNow - t._time) >= 0) t._call.call(void 0, e);
      t = t._next;
    }
    --frame;
  }
  __name(timerFlush, "timerFlush");
  function wake() {
    clockNow = (clockLast = clock.now()) + clockSkew;
    frame = timeout = 0;
    try {
      timerFlush();
    } finally {
      frame = 0;
      nap();
      clockNow = 0;
    }
  }
  __name(wake, "wake");
  function poke() {
    var now2 = clock.now(), delay = now2 - clockLast;
    if (delay > pokeDelay) clockSkew -= delay, clockLast = now2;
  }
  __name(poke, "poke");
  function nap() {
    var t0, t1 = taskHead, t2, time = Infinity;
    while (t1) {
      if (t1._call) {
        if (time > t1._time) time = t1._time;
        t0 = t1, t1 = t1._next;
      } else {
        t2 = t1._next, t1._next = null;
        t1 = t0 ? t0._next = t2 : taskHead = t2;
      }
    }
    taskTail = t0;
    sleep(time);
  }
  __name(nap, "nap");
  function sleep(time) {
    if (frame) return;
    if (timeout) timeout = clearTimeout(timeout);
    var delay = time - clockNow;
    if (delay > 24) {
      if (time < Infinity) timeout = setTimeout(wake, time - clock.now() - clockSkew);
      if (interval) interval = clearInterval(interval);
    } else {
      if (!interval) clockLast = clock.now(), interval = setInterval(poke, pokeDelay);
      frame = 1, setFrame(wake);
    }
  }
  __name(sleep, "sleep");

  // node_modules/d3-timer/src/timeout.js
  function timeout_default(callback, delay, time) {
    var t = new Timer();
    delay = delay == null ? 0 : +delay;
    t.restart((elapsed) => {
      t.stop();
      callback(elapsed + delay);
    }, delay, time);
    return t;
  }
  __name(timeout_default, "default");

  // node_modules/d3-transition/src/transition/schedule.js
  var emptyOn = dispatch_default2("start", "end", "cancel", "interrupt");
  var emptyTween = [];
  var CREATED = 0;
  var SCHEDULED = 1;
  var STARTING = 2;
  var STARTED = 3;
  var RUNNING = 4;
  var ENDING = 5;
  var ENDED = 6;
  function schedule_default(node, name, id2, index, group, timing) {
    var schedules = node.__transition;
    if (!schedules) node.__transition = {};
    else if (id2 in schedules) return;
    create(node, id2, {
      name,
      index,
      // For context during callback.
      group,
      // For context during callback.
      on: emptyOn,
      tween: emptyTween,
      time: timing.time,
      delay: timing.delay,
      duration: timing.duration,
      ease: timing.ease,
      timer: null,
      state: CREATED
    });
  }
  __name(schedule_default, "default");
  function init(node, id2) {
    var schedule = get2(node, id2);
    if (schedule.state > CREATED) throw new Error("too late; already scheduled");
    return schedule;
  }
  __name(init, "init");
  function set2(node, id2) {
    var schedule = get2(node, id2);
    if (schedule.state > STARTED) throw new Error("too late; already running");
    return schedule;
  }
  __name(set2, "set");
  function get2(node, id2) {
    var schedule = node.__transition;
    if (!schedule || !(schedule = schedule[id2])) throw new Error("transition not found");
    return schedule;
  }
  __name(get2, "get");
  function create(node, id2, self) {
    var schedules = node.__transition, tween;
    schedules[id2] = self;
    self.timer = timer(schedule, 0, self.time);
    function schedule(elapsed) {
      self.state = SCHEDULED;
      self.timer.restart(start2, self.delay, self.time);
      if (self.delay <= elapsed) start2(elapsed - self.delay);
    }
    __name(schedule, "schedule");
    function start2(elapsed) {
      var i, j, n, o;
      if (self.state !== SCHEDULED) return stop();
      for (i in schedules) {
        o = schedules[i];
        if (o.name !== self.name) continue;
        if (o.state === STARTED) return timeout_default(start2);
        if (o.state === RUNNING) {
          o.state = ENDED;
          o.timer.stop();
          o.on.call("interrupt", node, node.__data__, o.index, o.group);
          delete schedules[i];
        } else if (+i < id2) {
          o.state = ENDED;
          o.timer.stop();
          o.on.call("cancel", node, node.__data__, o.index, o.group);
          delete schedules[i];
        }
      }
      timeout_default(function() {
        if (self.state === STARTED) {
          self.state = RUNNING;
          self.timer.restart(tick, self.delay, self.time);
          tick(elapsed);
        }
      });
      self.state = STARTING;
      self.on.call("start", node, node.__data__, self.index, self.group);
      if (self.state !== STARTING) return;
      self.state = STARTED;
      tween = new Array(n = self.tween.length);
      for (i = 0, j = -1; i < n; ++i) {
        if (o = self.tween[i].value.call(node, node.__data__, self.index, self.group)) {
          tween[++j] = o;
        }
      }
      tween.length = j + 1;
    }
    __name(start2, "start");
    function tick(elapsed) {
      var t = elapsed < self.duration ? self.ease.call(null, elapsed / self.duration) : (self.timer.restart(stop), self.state = ENDING, 1), i = -1, n = tween.length;
      while (++i < n) {
        tween[i].call(node, t);
      }
      if (self.state === ENDING) {
        self.on.call("end", node, node.__data__, self.index, self.group);
        stop();
      }
    }
    __name(tick, "tick");
    function stop() {
      self.state = ENDED;
      self.timer.stop();
      delete schedules[id2];
      for (var i in schedules) return;
      delete node.__transition;
    }
    __name(stop, "stop");
  }
  __name(create, "create");

  // node_modules/d3-transition/src/interrupt.js
  function interrupt_default(node, name) {
    var schedules = node.__transition, schedule, active, empty2 = true, i;
    if (!schedules) return;
    name = name == null ? null : name + "";
    for (i in schedules) {
      if ((schedule = schedules[i]).name !== name) {
        empty2 = false;
        continue;
      }
      active = schedule.state > STARTING && schedule.state < ENDING;
      schedule.state = ENDED;
      schedule.timer.stop();
      schedule.on.call(active ? "interrupt" : "cancel", node, node.__data__, schedule.index, schedule.group);
      delete schedules[i];
    }
    if (empty2) delete node.__transition;
  }
  __name(interrupt_default, "default");

  // node_modules/d3-transition/src/selection/interrupt.js
  function interrupt_default2(name) {
    return this.each(function() {
      interrupt_default(this, name);
    });
  }
  __name(interrupt_default2, "default");

  // node_modules/d3-transition/src/transition/tween.js
  function tweenRemove(id2, name) {
    var tween0, tween1;
    return function() {
      var schedule = set2(this, id2), tween = schedule.tween;
      if (tween !== tween0) {
        tween1 = tween0 = tween;
        for (var i = 0, n = tween1.length; i < n; ++i) {
          if (tween1[i].name === name) {
            tween1 = tween1.slice();
            tween1.splice(i, 1);
            break;
          }
        }
      }
      schedule.tween = tween1;
    };
  }
  __name(tweenRemove, "tweenRemove");
  function tweenFunction(id2, name, value) {
    var tween0, tween1;
    if (typeof value !== "function") throw new Error();
    return function() {
      var schedule = set2(this, id2), tween = schedule.tween;
      if (tween !== tween0) {
        tween1 = (tween0 = tween).slice();
        for (var t = { name, value }, i = 0, n = tween1.length; i < n; ++i) {
          if (tween1[i].name === name) {
            tween1[i] = t;
            break;
          }
        }
        if (i === n) tween1.push(t);
      }
      schedule.tween = tween1;
    };
  }
  __name(tweenFunction, "tweenFunction");
  function tween_default(name, value) {
    var id2 = this._id;
    name += "";
    if (arguments.length < 2) {
      var tween = get2(this.node(), id2).tween;
      for (var i = 0, n = tween.length, t; i < n; ++i) {
        if ((t = tween[i]).name === name) {
          return t.value;
        }
      }
      return null;
    }
    return this.each((value == null ? tweenRemove : tweenFunction)(id2, name, value));
  }
  __name(tween_default, "default");
  function tweenValue(transition2, name, value) {
    var id2 = transition2._id;
    transition2.each(function() {
      var schedule = set2(this, id2);
      (schedule.value || (schedule.value = {}))[name] = value.apply(this, arguments);
    });
    return function(node) {
      return get2(node, id2).value[name];
    };
  }
  __name(tweenValue, "tweenValue");

  // node_modules/d3-transition/src/transition/interpolate.js
  function interpolate_default(a, b) {
    var c;
    return (typeof b === "number" ? number_default : b instanceof color ? rgb_default : (c = color(b)) ? (b = c, rgb_default) : string_default)(a, b);
  }
  __name(interpolate_default, "default");

  // node_modules/d3-transition/src/transition/attr.js
  function attrRemove2(name) {
    return function() {
      this.removeAttribute(name);
    };
  }
  __name(attrRemove2, "attrRemove");
  function attrRemoveNS2(fullname) {
    return function() {
      this.removeAttributeNS(fullname.space, fullname.local);
    };
  }
  __name(attrRemoveNS2, "attrRemoveNS");
  function attrConstant2(name, interpolate, value1) {
    var string00, string1 = value1 + "", interpolate0;
    return function() {
      var string0 = this.getAttribute(name);
      return string0 === string1 ? null : string0 === string00 ? interpolate0 : interpolate0 = interpolate(string00 = string0, value1);
    };
  }
  __name(attrConstant2, "attrConstant");
  function attrConstantNS2(fullname, interpolate, value1) {
    var string00, string1 = value1 + "", interpolate0;
    return function() {
      var string0 = this.getAttributeNS(fullname.space, fullname.local);
      return string0 === string1 ? null : string0 === string00 ? interpolate0 : interpolate0 = interpolate(string00 = string0, value1);
    };
  }
  __name(attrConstantNS2, "attrConstantNS");
  function attrFunction2(name, interpolate, value) {
    var string00, string10, interpolate0;
    return function() {
      var string0, value1 = value(this), string1;
      if (value1 == null) return void this.removeAttribute(name);
      string0 = this.getAttribute(name);
      string1 = value1 + "";
      return string0 === string1 ? null : string0 === string00 && string1 === string10 ? interpolate0 : (string10 = string1, interpolate0 = interpolate(string00 = string0, value1));
    };
  }
  __name(attrFunction2, "attrFunction");
  function attrFunctionNS2(fullname, interpolate, value) {
    var string00, string10, interpolate0;
    return function() {
      var string0, value1 = value(this), string1;
      if (value1 == null) return void this.removeAttributeNS(fullname.space, fullname.local);
      string0 = this.getAttributeNS(fullname.space, fullname.local);
      string1 = value1 + "";
      return string0 === string1 ? null : string0 === string00 && string1 === string10 ? interpolate0 : (string10 = string1, interpolate0 = interpolate(string00 = string0, value1));
    };
  }
  __name(attrFunctionNS2, "attrFunctionNS");
  function attr_default2(name, value) {
    var fullname = namespace_default(name), i = fullname === "transform" ? interpolateTransformSvg : interpolate_default;
    return this.attrTween(name, typeof value === "function" ? (fullname.local ? attrFunctionNS2 : attrFunction2)(fullname, i, tweenValue(this, "attr." + name, value)) : value == null ? (fullname.local ? attrRemoveNS2 : attrRemove2)(fullname) : (fullname.local ? attrConstantNS2 : attrConstant2)(fullname, i, value));
  }
  __name(attr_default2, "default");

  // node_modules/d3-transition/src/transition/attrTween.js
  function attrInterpolate(name, i) {
    return function(t) {
      this.setAttribute(name, i.call(this, t));
    };
  }
  __name(attrInterpolate, "attrInterpolate");
  function attrInterpolateNS(fullname, i) {
    return function(t) {
      this.setAttributeNS(fullname.space, fullname.local, i.call(this, t));
    };
  }
  __name(attrInterpolateNS, "attrInterpolateNS");
  function attrTweenNS(fullname, value) {
    var t0, i0;
    function tween() {
      var i = value.apply(this, arguments);
      if (i !== i0) t0 = (i0 = i) && attrInterpolateNS(fullname, i);
      return t0;
    }
    __name(tween, "tween");
    tween._value = value;
    return tween;
  }
  __name(attrTweenNS, "attrTweenNS");
  function attrTween(name, value) {
    var t0, i0;
    function tween() {
      var i = value.apply(this, arguments);
      if (i !== i0) t0 = (i0 = i) && attrInterpolate(name, i);
      return t0;
    }
    __name(tween, "tween");
    tween._value = value;
    return tween;
  }
  __name(attrTween, "attrTween");
  function attrTween_default(name, value) {
    var key = "attr." + name;
    if (arguments.length < 2) return (key = this.tween(key)) && key._value;
    if (value == null) return this.tween(key, null);
    if (typeof value !== "function") throw new Error();
    var fullname = namespace_default(name);
    return this.tween(key, (fullname.local ? attrTweenNS : attrTween)(fullname, value));
  }
  __name(attrTween_default, "default");

  // node_modules/d3-transition/src/transition/delay.js
  function delayFunction(id2, value) {
    return function() {
      init(this, id2).delay = +value.apply(this, arguments);
    };
  }
  __name(delayFunction, "delayFunction");
  function delayConstant(id2, value) {
    return value = +value, function() {
      init(this, id2).delay = value;
    };
  }
  __name(delayConstant, "delayConstant");
  function delay_default(value) {
    var id2 = this._id;
    return arguments.length ? this.each((typeof value === "function" ? delayFunction : delayConstant)(id2, value)) : get2(this.node(), id2).delay;
  }
  __name(delay_default, "default");

  // node_modules/d3-transition/src/transition/duration.js
  function durationFunction(id2, value) {
    return function() {
      set2(this, id2).duration = +value.apply(this, arguments);
    };
  }
  __name(durationFunction, "durationFunction");
  function durationConstant(id2, value) {
    return value = +value, function() {
      set2(this, id2).duration = value;
    };
  }
  __name(durationConstant, "durationConstant");
  function duration_default(value) {
    var id2 = this._id;
    return arguments.length ? this.each((typeof value === "function" ? durationFunction : durationConstant)(id2, value)) : get2(this.node(), id2).duration;
  }
  __name(duration_default, "default");

  // node_modules/d3-transition/src/transition/ease.js
  function easeConstant(id2, value) {
    if (typeof value !== "function") throw new Error();
    return function() {
      set2(this, id2).ease = value;
    };
  }
  __name(easeConstant, "easeConstant");
  function ease_default(value) {
    var id2 = this._id;
    return arguments.length ? this.each(easeConstant(id2, value)) : get2(this.node(), id2).ease;
  }
  __name(ease_default, "default");

  // node_modules/d3-transition/src/transition/easeVarying.js
  function easeVarying(id2, value) {
    return function() {
      var v = value.apply(this, arguments);
      if (typeof v !== "function") throw new Error();
      set2(this, id2).ease = v;
    };
  }
  __name(easeVarying, "easeVarying");
  function easeVarying_default(value) {
    if (typeof value !== "function") throw new Error();
    return this.each(easeVarying(this._id, value));
  }
  __name(easeVarying_default, "default");

  // node_modules/d3-transition/src/transition/filter.js
  function filter_default2(match) {
    if (typeof match !== "function") match = matcher_default(match);
    for (var groups = this._groups, m = groups.length, subgroups = new Array(m), j = 0; j < m; ++j) {
      for (var group = groups[j], n = group.length, subgroup = subgroups[j] = [], node, i = 0; i < n; ++i) {
        if ((node = group[i]) && match.call(node, node.__data__, i, group)) {
          subgroup.push(node);
        }
      }
    }
    return new Transition(subgroups, this._parents, this._name, this._id);
  }
  __name(filter_default2, "default");

  // node_modules/d3-transition/src/transition/merge.js
  function merge_default2(transition2) {
    if (transition2._id !== this._id) throw new Error();
    for (var groups0 = this._groups, groups1 = transition2._groups, m0 = groups0.length, m1 = groups1.length, m = Math.min(m0, m1), merges = new Array(m0), j = 0; j < m; ++j) {
      for (var group0 = groups0[j], group1 = groups1[j], n = group0.length, merge = merges[j] = new Array(n), node, i = 0; i < n; ++i) {
        if (node = group0[i] || group1[i]) {
          merge[i] = node;
        }
      }
    }
    for (; j < m0; ++j) {
      merges[j] = groups0[j];
    }
    return new Transition(merges, this._parents, this._name, this._id);
  }
  __name(merge_default2, "default");

  // node_modules/d3-transition/src/transition/on.js
  function start(name) {
    return (name + "").trim().split(/^|\s+/).every(function(t) {
      var i = t.indexOf(".");
      if (i >= 0) t = t.slice(0, i);
      return !t || t === "start";
    });
  }
  __name(start, "start");
  function onFunction(id2, name, listener) {
    var on0, on1, sit = start(name) ? init : set2;
    return function() {
      var schedule = sit(this, id2), on = schedule.on;
      if (on !== on0) (on1 = (on0 = on).copy()).on(name, listener);
      schedule.on = on1;
    };
  }
  __name(onFunction, "onFunction");
  function on_default2(name, listener) {
    var id2 = this._id;
    return arguments.length < 2 ? get2(this.node(), id2).on.on(name) : this.each(onFunction(id2, name, listener));
  }
  __name(on_default2, "default");

  // node_modules/d3-transition/src/transition/remove.js
  function removeFunction(id2) {
    return function() {
      var parent = this.parentNode;
      for (var i in this.__transition) if (+i !== id2) return;
      if (parent) parent.removeChild(this);
    };
  }
  __name(removeFunction, "removeFunction");
  function remove_default2() {
    return this.on("end.remove", removeFunction(this._id));
  }
  __name(remove_default2, "default");

  // node_modules/d3-transition/src/transition/select.js
  function select_default3(select) {
    var name = this._name, id2 = this._id;
    if (typeof select !== "function") select = selector_default(select);
    for (var groups = this._groups, m = groups.length, subgroups = new Array(m), j = 0; j < m; ++j) {
      for (var group = groups[j], n = group.length, subgroup = subgroups[j] = new Array(n), node, subnode, i = 0; i < n; ++i) {
        if ((node = group[i]) && (subnode = select.call(node, node.__data__, i, group))) {
          if ("__data__" in node) subnode.__data__ = node.__data__;
          subgroup[i] = subnode;
          schedule_default(subgroup[i], name, id2, i, subgroup, get2(node, id2));
        }
      }
    }
    return new Transition(subgroups, this._parents, name, id2);
  }
  __name(select_default3, "default");

  // node_modules/d3-transition/src/transition/selectAll.js
  function selectAll_default3(select) {
    var name = this._name, id2 = this._id;
    if (typeof select !== "function") select = selectorAll_default(select);
    for (var groups = this._groups, m = groups.length, subgroups = [], parents = [], j = 0; j < m; ++j) {
      for (var group = groups[j], n = group.length, node, i = 0; i < n; ++i) {
        if (node = group[i]) {
          for (var children2 = select.call(node, node.__data__, i, group), child, inherit2 = get2(node, id2), k = 0, l = children2.length; k < l; ++k) {
            if (child = children2[k]) {
              schedule_default(child, name, id2, k, children2, inherit2);
            }
          }
          subgroups.push(children2);
          parents.push(node);
        }
      }
    }
    return new Transition(subgroups, parents, name, id2);
  }
  __name(selectAll_default3, "default");

  // node_modules/d3-transition/src/transition/selection.js
  var Selection2 = selection_default.prototype.constructor;
  function selection_default2() {
    return new Selection2(this._groups, this._parents);
  }
  __name(selection_default2, "default");

  // node_modules/d3-transition/src/transition/style.js
  function styleNull(name, interpolate) {
    var string00, string10, interpolate0;
    return function() {
      var string0 = styleValue(this, name), string1 = (this.style.removeProperty(name), styleValue(this, name));
      return string0 === string1 ? null : string0 === string00 && string1 === string10 ? interpolate0 : interpolate0 = interpolate(string00 = string0, string10 = string1);
    };
  }
  __name(styleNull, "styleNull");
  function styleRemove2(name) {
    return function() {
      this.style.removeProperty(name);
    };
  }
  __name(styleRemove2, "styleRemove");
  function styleConstant2(name, interpolate, value1) {
    var string00, string1 = value1 + "", interpolate0;
    return function() {
      var string0 = styleValue(this, name);
      return string0 === string1 ? null : string0 === string00 ? interpolate0 : interpolate0 = interpolate(string00 = string0, value1);
    };
  }
  __name(styleConstant2, "styleConstant");
  function styleFunction2(name, interpolate, value) {
    var string00, string10, interpolate0;
    return function() {
      var string0 = styleValue(this, name), value1 = value(this), string1 = value1 + "";
      if (value1 == null) string1 = value1 = (this.style.removeProperty(name), styleValue(this, name));
      return string0 === string1 ? null : string0 === string00 && string1 === string10 ? interpolate0 : (string10 = string1, interpolate0 = interpolate(string00 = string0, value1));
    };
  }
  __name(styleFunction2, "styleFunction");
  function styleMaybeRemove(id2, name) {
    var on0, on1, listener0, key = "style." + name, event = "end." + key, remove2;
    return function() {
      var schedule = set2(this, id2), on = schedule.on, listener = schedule.value[key] == null ? remove2 || (remove2 = styleRemove2(name)) : void 0;
      if (on !== on0 || listener0 !== listener) (on1 = (on0 = on).copy()).on(event, listener0 = listener);
      schedule.on = on1;
    };
  }
  __name(styleMaybeRemove, "styleMaybeRemove");
  function style_default2(name, value, priority) {
    var i = (name += "") === "transform" ? interpolateTransformCss : interpolate_default;
    return value == null ? this.styleTween(name, styleNull(name, i)).on("end.style." + name, styleRemove2(name)) : typeof value === "function" ? this.styleTween(name, styleFunction2(name, i, tweenValue(this, "style." + name, value))).each(styleMaybeRemove(this._id, name)) : this.styleTween(name, styleConstant2(name, i, value), priority).on("end.style." + name, null);
  }
  __name(style_default2, "default");

  // node_modules/d3-transition/src/transition/styleTween.js
  function styleInterpolate(name, i, priority) {
    return function(t) {
      this.style.setProperty(name, i.call(this, t), priority);
    };
  }
  __name(styleInterpolate, "styleInterpolate");
  function styleTween(name, value, priority) {
    var t, i0;
    function tween() {
      var i = value.apply(this, arguments);
      if (i !== i0) t = (i0 = i) && styleInterpolate(name, i, priority);
      return t;
    }
    __name(tween, "tween");
    tween._value = value;
    return tween;
  }
  __name(styleTween, "styleTween");
  function styleTween_default(name, value, priority) {
    var key = "style." + (name += "");
    if (arguments.length < 2) return (key = this.tween(key)) && key._value;
    if (value == null) return this.tween(key, null);
    if (typeof value !== "function") throw new Error();
    return this.tween(key, styleTween(name, value, priority == null ? "" : priority));
  }
  __name(styleTween_default, "default");

  // node_modules/d3-transition/src/transition/text.js
  function textConstant2(value) {
    return function() {
      this.textContent = value;
    };
  }
  __name(textConstant2, "textConstant");
  function textFunction2(value) {
    return function() {
      var value1 = value(this);
      this.textContent = value1 == null ? "" : value1;
    };
  }
  __name(textFunction2, "textFunction");
  function text_default2(value) {
    return this.tween("text", typeof value === "function" ? textFunction2(tweenValue(this, "text", value)) : textConstant2(value == null ? "" : value + ""));
  }
  __name(text_default2, "default");

  // node_modules/d3-transition/src/transition/textTween.js
  function textInterpolate(i) {
    return function(t) {
      this.textContent = i.call(this, t);
    };
  }
  __name(textInterpolate, "textInterpolate");
  function textTween(value) {
    var t0, i0;
    function tween() {
      var i = value.apply(this, arguments);
      if (i !== i0) t0 = (i0 = i) && textInterpolate(i);
      return t0;
    }
    __name(tween, "tween");
    tween._value = value;
    return tween;
  }
  __name(textTween, "textTween");
  function textTween_default(value) {
    var key = "text";
    if (arguments.length < 1) return (key = this.tween(key)) && key._value;
    if (value == null) return this.tween(key, null);
    if (typeof value !== "function") throw new Error();
    return this.tween(key, textTween(value));
  }
  __name(textTween_default, "default");

  // node_modules/d3-transition/src/transition/transition.js
  function transition_default() {
    var name = this._name, id0 = this._id, id1 = newId();
    for (var groups = this._groups, m = groups.length, j = 0; j < m; ++j) {
      for (var group = groups[j], n = group.length, node, i = 0; i < n; ++i) {
        if (node = group[i]) {
          var inherit2 = get2(node, id0);
          schedule_default(node, name, id1, i, group, {
            time: inherit2.time + inherit2.delay + inherit2.duration,
            delay: 0,
            duration: inherit2.duration,
            ease: inherit2.ease
          });
        }
      }
    }
    return new Transition(groups, this._parents, name, id1);
  }
  __name(transition_default, "default");

  // node_modules/d3-transition/src/transition/end.js
  function end_default() {
    var on0, on1, that = this, id2 = that._id, size = that.size();
    return new Promise(function(resolve, reject) {
      var cancel = { value: reject }, end = { value: /* @__PURE__ */ __name(function() {
        if (--size === 0) resolve();
      }, "value") };
      that.each(function() {
        var schedule = set2(this, id2), on = schedule.on;
        if (on !== on0) {
          on1 = (on0 = on).copy();
          on1._.cancel.push(cancel);
          on1._.interrupt.push(cancel);
          on1._.end.push(end);
        }
        schedule.on = on1;
      });
      if (size === 0) resolve();
    });
  }
  __name(end_default, "default");

  // node_modules/d3-transition/src/transition/index.js
  var id = 0;
  function Transition(groups, parents, name, id2) {
    this._groups = groups;
    this._parents = parents;
    this._name = name;
    this._id = id2;
  }
  __name(Transition, "Transition");
  function transition(name) {
    return selection_default().transition(name);
  }
  __name(transition, "transition");
  function newId() {
    return ++id;
  }
  __name(newId, "newId");
  var selection_prototype = selection_default.prototype;
  Transition.prototype = transition.prototype = {
    constructor: Transition,
    select: select_default3,
    selectAll: selectAll_default3,
    selectChild: selection_prototype.selectChild,
    selectChildren: selection_prototype.selectChildren,
    filter: filter_default2,
    merge: merge_default2,
    selection: selection_default2,
    transition: transition_default,
    call: selection_prototype.call,
    nodes: selection_prototype.nodes,
    node: selection_prototype.node,
    size: selection_prototype.size,
    empty: selection_prototype.empty,
    each: selection_prototype.each,
    on: on_default2,
    attr: attr_default2,
    attrTween: attrTween_default,
    style: style_default2,
    styleTween: styleTween_default,
    text: text_default2,
    textTween: textTween_default,
    remove: remove_default2,
    tween: tween_default,
    delay: delay_default,
    duration: duration_default,
    ease: ease_default,
    easeVarying: easeVarying_default,
    end: end_default,
    [Symbol.iterator]: selection_prototype[Symbol.iterator]
  };

  // node_modules/d3-ease/src/cubic.js
  function cubicInOut(t) {
    return ((t *= 2) <= 1 ? t * t * t : (t -= 2) * t * t + 2) / 2;
  }
  __name(cubicInOut, "cubicInOut");

  // node_modules/d3-transition/src/selection/transition.js
  var defaultTiming = {
    time: null,
    // Set on use.
    delay: 0,
    duration: 250,
    ease: cubicInOut
  };
  function inherit(node, id2) {
    var timing;
    while (!(timing = node.__transition) || !(timing = timing[id2])) {
      if (!(node = node.parentNode)) {
        throw new Error(`transition ${id2} not found`);
      }
    }
    return timing;
  }
  __name(inherit, "inherit");
  function transition_default2(name) {
    var id2, timing;
    if (name instanceof Transition) {
      id2 = name._id, name = name._name;
    } else {
      id2 = newId(), (timing = defaultTiming).time = now(), name = name == null ? null : name + "";
    }
    for (var groups = this._groups, m = groups.length, j = 0; j < m; ++j) {
      for (var group = groups[j], n = group.length, node, i = 0; i < n; ++i) {
        if (node = group[i]) {
          schedule_default(node, name, id2, i, group, timing || inherit(node, id2));
        }
      }
    }
    return new Transition(groups, this._parents, name, id2);
  }
  __name(transition_default2, "default");

  // node_modules/d3-transition/src/selection/index.js
  selection_default.prototype.interrupt = interrupt_default2;
  selection_default.prototype.transition = transition_default2;

  // node_modules/d3-zoom/src/constant.js
  var constant_default4 = /* @__PURE__ */ __name((x) => () => x, "default");

  // node_modules/d3-zoom/src/event.js
  function ZoomEvent(type, {
    sourceEvent,
    target,
    transform: transform2,
    dispatch: dispatch2
  }) {
    Object.defineProperties(this, {
      type: { value: type, enumerable: true, configurable: true },
      sourceEvent: { value: sourceEvent, enumerable: true, configurable: true },
      target: { value: target, enumerable: true, configurable: true },
      transform: { value: transform2, enumerable: true, configurable: true },
      _: { value: dispatch2 }
    });
  }
  __name(ZoomEvent, "ZoomEvent");

  // node_modules/d3-zoom/src/transform.js
  function Transform(k, x, y) {
    this.k = k;
    this.x = x;
    this.y = y;
  }
  __name(Transform, "Transform");
  Transform.prototype = {
    constructor: Transform,
    scale: /* @__PURE__ */ __name(function(k) {
      return k === 1 ? this : new Transform(this.k * k, this.x, this.y);
    }, "scale"),
    translate: /* @__PURE__ */ __name(function(x, y) {
      return x === 0 & y === 0 ? this : new Transform(this.k, this.x + this.k * x, this.y + this.k * y);
    }, "translate"),
    apply: /* @__PURE__ */ __name(function(point) {
      return [point[0] * this.k + this.x, point[1] * this.k + this.y];
    }, "apply"),
    applyX: /* @__PURE__ */ __name(function(x) {
      return x * this.k + this.x;
    }, "applyX"),
    applyY: /* @__PURE__ */ __name(function(y) {
      return y * this.k + this.y;
    }, "applyY"),
    invert: /* @__PURE__ */ __name(function(location) {
      return [(location[0] - this.x) / this.k, (location[1] - this.y) / this.k];
    }, "invert"),
    invertX: /* @__PURE__ */ __name(function(x) {
      return (x - this.x) / this.k;
    }, "invertX"),
    invertY: /* @__PURE__ */ __name(function(y) {
      return (y - this.y) / this.k;
    }, "invertY"),
    rescaleX: /* @__PURE__ */ __name(function(x) {
      return x.copy().domain(x.range().map(this.invertX, this).map(x.invert, x));
    }, "rescaleX"),
    rescaleY: /* @__PURE__ */ __name(function(y) {
      return y.copy().domain(y.range().map(this.invertY, this).map(y.invert, y));
    }, "rescaleY"),
    toString: /* @__PURE__ */ __name(function() {
      return "translate(" + this.x + "," + this.y + ") scale(" + this.k + ")";
    }, "toString")
  };
  var identity2 = new Transform(1, 0, 0);
  transform.prototype = Transform.prototype;
  function transform(node) {
    while (!node.__zoom) if (!(node = node.parentNode)) return identity2;
    return node.__zoom;
  }
  __name(transform, "transform");

  // node_modules/d3-zoom/src/noevent.js
  function nopropagation(event) {
    event.stopImmediatePropagation();
  }
  __name(nopropagation, "nopropagation");
  function noevent_default2(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
  }
  __name(noevent_default2, "default");

  // node_modules/d3-zoom/src/zoom.js
  function defaultFilter(event) {
    return (!event.ctrlKey || event.type === "wheel") && !event.button;
  }
  __name(defaultFilter, "defaultFilter");
  function defaultExtent() {
    var e = this;
    if (e instanceof SVGElement) {
      e = e.ownerSVGElement || e;
      if (e.hasAttribute("viewBox")) {
        e = e.viewBox.baseVal;
        return [[e.x, e.y], [e.x + e.width, e.y + e.height]];
      }
      return [[0, 0], [e.width.baseVal.value, e.height.baseVal.value]];
    }
    return [[0, 0], [e.clientWidth, e.clientHeight]];
  }
  __name(defaultExtent, "defaultExtent");
  function defaultTransform() {
    return this.__zoom || identity2;
  }
  __name(defaultTransform, "defaultTransform");
  function defaultWheelDelta(event) {
    return -event.deltaY * (event.deltaMode === 1 ? 0.05 : event.deltaMode ? 1 : 2e-3) * (event.ctrlKey ? 10 : 1);
  }
  __name(defaultWheelDelta, "defaultWheelDelta");
  function defaultTouchable() {
    return navigator.maxTouchPoints || "ontouchstart" in this;
  }
  __name(defaultTouchable, "defaultTouchable");
  function defaultConstrain(transform2, extent, translateExtent) {
    var dx0 = transform2.invertX(extent[0][0]) - translateExtent[0][0], dx1 = transform2.invertX(extent[1][0]) - translateExtent[1][0], dy0 = transform2.invertY(extent[0][1]) - translateExtent[0][1], dy1 = transform2.invertY(extent[1][1]) - translateExtent[1][1];
    return transform2.translate(
      dx1 > dx0 ? (dx0 + dx1) / 2 : Math.min(0, dx0) || Math.max(0, dx1),
      dy1 > dy0 ? (dy0 + dy1) / 2 : Math.min(0, dy0) || Math.max(0, dy1)
    );
  }
  __name(defaultConstrain, "defaultConstrain");
  function zoom_default2() {
    var filter2 = defaultFilter, extent = defaultExtent, constrain = defaultConstrain, wheelDelta = defaultWheelDelta, touchable = defaultTouchable, scaleExtent = [0, Infinity], translateExtent = [[-Infinity, -Infinity], [Infinity, Infinity]], duration = 250, interpolate = zoom_default, listeners = dispatch_default2("start", "zoom", "end"), touchstarting, touchfirst, touchending, touchDelay = 500, wheelDelay = 150, clickDistance2 = 0, tapDistance = 10;
    function zoom(selection2) {
      selection2.property("__zoom", defaultTransform).on("wheel.zoom", wheeled, { passive: false }).on("mousedown.zoom", mousedowned).on("dblclick.zoom", dblclicked).filter(touchable).on("touchstart.zoom", touchstarted).on("touchmove.zoom", touchmoved).on("touchend.zoom touchcancel.zoom", touchended).style("-webkit-tap-highlight-color", "rgba(0,0,0,0)");
    }
    __name(zoom, "zoom");
    zoom.transform = function(collection, transform2, point, event) {
      var selection2 = collection.selection ? collection.selection() : collection;
      selection2.property("__zoom", defaultTransform);
      if (collection !== selection2) {
        schedule(collection, transform2, point, event);
      } else {
        selection2.interrupt().each(function() {
          gesture(this, arguments).event(event).start().zoom(null, typeof transform2 === "function" ? transform2.apply(this, arguments) : transform2).end();
        });
      }
    };
    zoom.scaleBy = function(selection2, k, p, event) {
      zoom.scaleTo(selection2, function() {
        var k0 = this.__zoom.k, k1 = typeof k === "function" ? k.apply(this, arguments) : k;
        return k0 * k1;
      }, p, event);
    };
    zoom.scaleTo = function(selection2, k, p, event) {
      zoom.transform(selection2, function() {
        var e = extent.apply(this, arguments), t0 = this.__zoom, p0 = p == null ? centroid(e) : typeof p === "function" ? p.apply(this, arguments) : p, p1 = t0.invert(p0), k1 = typeof k === "function" ? k.apply(this, arguments) : k;
        return constrain(translate(scale(t0, k1), p0, p1), e, translateExtent);
      }, p, event);
    };
    zoom.translateBy = function(selection2, x, y, event) {
      zoom.transform(selection2, function() {
        return constrain(this.__zoom.translate(
          typeof x === "function" ? x.apply(this, arguments) : x,
          typeof y === "function" ? y.apply(this, arguments) : y
        ), extent.apply(this, arguments), translateExtent);
      }, null, event);
    };
    zoom.translateTo = function(selection2, x, y, p, event) {
      zoom.transform(selection2, function() {
        var e = extent.apply(this, arguments), t = this.__zoom, p0 = p == null ? centroid(e) : typeof p === "function" ? p.apply(this, arguments) : p;
        return constrain(identity2.translate(p0[0], p0[1]).scale(t.k).translate(
          typeof x === "function" ? -x.apply(this, arguments) : -x,
          typeof y === "function" ? -y.apply(this, arguments) : -y
        ), e, translateExtent);
      }, p, event);
    };
    function scale(transform2, k) {
      k = Math.max(scaleExtent[0], Math.min(scaleExtent[1], k));
      return k === transform2.k ? transform2 : new Transform(k, transform2.x, transform2.y);
    }
    __name(scale, "scale");
    function translate(transform2, p0, p1) {
      var x = p0[0] - p1[0] * transform2.k, y = p0[1] - p1[1] * transform2.k;
      return x === transform2.x && y === transform2.y ? transform2 : new Transform(transform2.k, x, y);
    }
    __name(translate, "translate");
    function centroid(extent2) {
      return [(+extent2[0][0] + +extent2[1][0]) / 2, (+extent2[0][1] + +extent2[1][1]) / 2];
    }
    __name(centroid, "centroid");
    function schedule(transition2, transform2, point, event) {
      transition2.on("start.zoom", function() {
        gesture(this, arguments).event(event).start();
      }).on("interrupt.zoom end.zoom", function() {
        gesture(this, arguments).event(event).end();
      }).tween("zoom", function() {
        var that = this, args = arguments, g = gesture(that, args).event(event), e = extent.apply(that, args), p = point == null ? centroid(e) : typeof point === "function" ? point.apply(that, args) : point, w = Math.max(e[1][0] - e[0][0], e[1][1] - e[0][1]), a = that.__zoom, b = typeof transform2 === "function" ? transform2.apply(that, args) : transform2, i = interpolate(a.invert(p).concat(w / a.k), b.invert(p).concat(w / b.k));
        return function(t) {
          if (t === 1) t = b;
          else {
            var l = i(t), k = w / l[2];
            t = new Transform(k, p[0] - l[0] * k, p[1] - l[1] * k);
          }
          g.zoom(null, t);
        };
      });
    }
    __name(schedule, "schedule");
    function gesture(that, args, clean) {
      return !clean && that.__zooming || new Gesture(that, args);
    }
    __name(gesture, "gesture");
    function Gesture(that, args) {
      this.that = that;
      this.args = args;
      this.active = 0;
      this.sourceEvent = null;
      this.extent = extent.apply(that, args);
      this.taps = 0;
    }
    __name(Gesture, "Gesture");
    Gesture.prototype = {
      event: /* @__PURE__ */ __name(function(event) {
        if (event) this.sourceEvent = event;
        return this;
      }, "event"),
      start: /* @__PURE__ */ __name(function() {
        if (++this.active === 1) {
          this.that.__zooming = this;
          this.emit("start");
        }
        return this;
      }, "start"),
      zoom: /* @__PURE__ */ __name(function(key, transform2) {
        if (this.mouse && key !== "mouse") this.mouse[1] = transform2.invert(this.mouse[0]);
        if (this.touch0 && key !== "touch") this.touch0[1] = transform2.invert(this.touch0[0]);
        if (this.touch1 && key !== "touch") this.touch1[1] = transform2.invert(this.touch1[0]);
        this.that.__zoom = transform2;
        this.emit("zoom");
        return this;
      }, "zoom"),
      end: /* @__PURE__ */ __name(function() {
        if (--this.active === 0) {
          delete this.that.__zooming;
          this.emit("end");
        }
        return this;
      }, "end"),
      emit: /* @__PURE__ */ __name(function(type) {
        var d = select_default2(this.that).datum();
        listeners.call(
          type,
          this.that,
          new ZoomEvent(type, {
            sourceEvent: this.sourceEvent,
            target: zoom,
            type,
            transform: this.that.__zoom,
            dispatch: listeners
          }),
          d
        );
      }, "emit")
    };
    function wheeled(event, ...args) {
      if (!filter2.apply(this, arguments)) return;
      var g = gesture(this, args).event(event), t = this.__zoom, k = Math.max(scaleExtent[0], Math.min(scaleExtent[1], t.k * Math.pow(2, wheelDelta.apply(this, arguments)))), p = pointer_default(event);
      if (g.wheel) {
        if (g.mouse[0][0] !== p[0] || g.mouse[0][1] !== p[1]) {
          g.mouse[1] = t.invert(g.mouse[0] = p);
        }
        clearTimeout(g.wheel);
      } else if (t.k === k) return;
      else {
        g.mouse = [p, t.invert(p)];
        interrupt_default(this);
        g.start();
      }
      noevent_default2(event);
      g.wheel = setTimeout(wheelidled, wheelDelay);
      g.zoom("mouse", constrain(translate(scale(t, k), g.mouse[0], g.mouse[1]), g.extent, translateExtent));
      function wheelidled() {
        g.wheel = null;
        g.end();
      }
      __name(wheelidled, "wheelidled");
    }
    __name(wheeled, "wheeled");
    function mousedowned(event, ...args) {
      if (touchending || !filter2.apply(this, arguments)) return;
      var currentTarget = event.currentTarget, g = gesture(this, args, true).event(event), v = select_default2(event.view).on("mousemove.zoom", mousemoved, true).on("mouseup.zoom", mouseupped, true), p = pointer_default(event, currentTarget), x0 = event.clientX, y0 = event.clientY;
      nodrag_default(event.view);
      nopropagation(event);
      g.mouse = [p, this.__zoom.invert(p)];
      interrupt_default(this);
      g.start();
      function mousemoved(event2) {
        noevent_default2(event2);
        if (!g.moved) {
          var dx = event2.clientX - x0, dy = event2.clientY - y0;
          g.moved = dx * dx + dy * dy > clickDistance2;
        }
        g.event(event2).zoom("mouse", constrain(translate(g.that.__zoom, g.mouse[0] = pointer_default(event2, currentTarget), g.mouse[1]), g.extent, translateExtent));
      }
      __name(mousemoved, "mousemoved");
      function mouseupped(event2) {
        v.on("mousemove.zoom mouseup.zoom", null);
        yesdrag(event2.view, g.moved);
        noevent_default2(event2);
        g.event(event2).end();
      }
      __name(mouseupped, "mouseupped");
    }
    __name(mousedowned, "mousedowned");
    function dblclicked(event, ...args) {
      if (!filter2.apply(this, arguments)) return;
      var t0 = this.__zoom, p0 = pointer_default(event.changedTouches ? event.changedTouches[0] : event, this), p1 = t0.invert(p0), k1 = t0.k * (event.shiftKey ? 0.5 : 2), t1 = constrain(translate(scale(t0, k1), p0, p1), extent.apply(this, args), translateExtent);
      noevent_default2(event);
      if (duration > 0) select_default2(this).transition().duration(duration).call(schedule, t1, p0, event);
      else select_default2(this).call(zoom.transform, t1, p0, event);
    }
    __name(dblclicked, "dblclicked");
    function touchstarted(event, ...args) {
      if (!filter2.apply(this, arguments)) return;
      var touches = event.touches, n = touches.length, g = gesture(this, args, event.changedTouches.length === n).event(event), started, i, t, p;
      nopropagation(event);
      for (i = 0; i < n; ++i) {
        t = touches[i], p = pointer_default(t, this);
        p = [p, this.__zoom.invert(p), t.identifier];
        if (!g.touch0) g.touch0 = p, started = true, g.taps = 1 + !!touchstarting;
        else if (!g.touch1 && g.touch0[2] !== p[2]) g.touch1 = p, g.taps = 0;
      }
      if (touchstarting) touchstarting = clearTimeout(touchstarting);
      if (started) {
        if (g.taps < 2) touchfirst = p[0], touchstarting = setTimeout(function() {
          touchstarting = null;
        }, touchDelay);
        interrupt_default(this);
        g.start();
      }
    }
    __name(touchstarted, "touchstarted");
    function touchmoved(event, ...args) {
      if (!this.__zooming) return;
      var g = gesture(this, args).event(event), touches = event.changedTouches, n = touches.length, i, t, p, l;
      noevent_default2(event);
      for (i = 0; i < n; ++i) {
        t = touches[i], p = pointer_default(t, this);
        if (g.touch0 && g.touch0[2] === t.identifier) g.touch0[0] = p;
        else if (g.touch1 && g.touch1[2] === t.identifier) g.touch1[0] = p;
      }
      t = g.that.__zoom;
      if (g.touch1) {
        var p0 = g.touch0[0], l0 = g.touch0[1], p1 = g.touch1[0], l1 = g.touch1[1], dp = (dp = p1[0] - p0[0]) * dp + (dp = p1[1] - p0[1]) * dp, dl = (dl = l1[0] - l0[0]) * dl + (dl = l1[1] - l0[1]) * dl;
        t = scale(t, Math.sqrt(dp / dl));
        p = [(p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2];
        l = [(l0[0] + l1[0]) / 2, (l0[1] + l1[1]) / 2];
      } else if (g.touch0) p = g.touch0[0], l = g.touch0[1];
      else return;
      g.zoom("touch", constrain(translate(t, p, l), g.extent, translateExtent));
    }
    __name(touchmoved, "touchmoved");
    function touchended(event, ...args) {
      if (!this.__zooming) return;
      var g = gesture(this, args).event(event), touches = event.changedTouches, n = touches.length, i, t;
      nopropagation(event);
      if (touchending) clearTimeout(touchending);
      touchending = setTimeout(function() {
        touchending = null;
      }, touchDelay);
      for (i = 0; i < n; ++i) {
        t = touches[i];
        if (g.touch0 && g.touch0[2] === t.identifier) delete g.touch0;
        else if (g.touch1 && g.touch1[2] === t.identifier) delete g.touch1;
      }
      if (g.touch1 && !g.touch0) g.touch0 = g.touch1, delete g.touch1;
      if (g.touch0) g.touch0[1] = this.__zoom.invert(g.touch0[0]);
      else {
        g.end();
        if (g.taps === 2) {
          t = pointer_default(t, this);
          if (Math.hypot(touchfirst[0] - t[0], touchfirst[1] - t[1]) < tapDistance) {
            var p = select_default2(this).on("dblclick.zoom");
            if (p) p.apply(this, arguments);
          }
        }
      }
    }
    __name(touchended, "touchended");
    zoom.wheelDelta = function(_) {
      return arguments.length ? (wheelDelta = typeof _ === "function" ? _ : constant_default4(+_), zoom) : wheelDelta;
    };
    zoom.filter = function(_) {
      return arguments.length ? (filter2 = typeof _ === "function" ? _ : constant_default4(!!_), zoom) : filter2;
    };
    zoom.touchable = function(_) {
      return arguments.length ? (touchable = typeof _ === "function" ? _ : constant_default4(!!_), zoom) : touchable;
    };
    zoom.extent = function(_) {
      return arguments.length ? (extent = typeof _ === "function" ? _ : constant_default4([[+_[0][0], +_[0][1]], [+_[1][0], +_[1][1]]]), zoom) : extent;
    };
    zoom.scaleExtent = function(_) {
      return arguments.length ? (scaleExtent[0] = +_[0], scaleExtent[1] = +_[1], zoom) : [scaleExtent[0], scaleExtent[1]];
    };
    zoom.translateExtent = function(_) {
      return arguments.length ? (translateExtent[0][0] = +_[0][0], translateExtent[1][0] = +_[1][0], translateExtent[0][1] = +_[0][1], translateExtent[1][1] = +_[1][1], zoom) : [[translateExtent[0][0], translateExtent[0][1]], [translateExtent[1][0], translateExtent[1][1]]];
    };
    zoom.constrain = function(_) {
      return arguments.length ? (constrain = _, zoom) : constrain;
    };
    zoom.duration = function(_) {
      return arguments.length ? (duration = +_, zoom) : duration;
    };
    zoom.interpolate = function(_) {
      return arguments.length ? (interpolate = _, zoom) : interpolate;
    };
    zoom.on = function() {
      var value = listeners.on.apply(listeners, arguments);
      return value === listeners ? zoom : value;
    };
    zoom.clickDistance = function(_) {
      return arguments.length ? (clickDistance2 = (_ = +_) * _, zoom) : Math.sqrt(clickDistance2);
    };
    zoom.tapDistance = function(_) {
      return arguments.length ? (tapDistance = +_, zoom) : tapDistance;
    };
    return zoom;
  }
  __name(zoom_default2, "default");

  // src/d3.ts
  var d3_default = {
    hierarchy,
    stratify: stratify_default,
    tree: tree_default,
    treemap: treemap_default,
    select: select_default2,
    selectAll: selectAll_default2,
    zoom: zoom_default2
  };

  // src/utils.ts
  var getAreaSize = /* @__PURE__ */ __name((htmlId) => {
    const SVGContainer = document.querySelector(`#${htmlId}`);
    if (SVGContainer === null) {
      throw new Error(`Cannot find dom element with id:${htmlId}`);
    }
    const areaWidth = SVGContainer.clientWidth;
    const areaHeight = SVGContainer.clientHeight;
    if (areaHeight === 0 || areaWidth === 0) {
      throw new Error(
        "The tree can't be display because the svg height or width of the container is null"
      );
    }
    return { areaWidth, areaHeight };
  }, "getAreaSize");
  var getFirstDisplayedAncestor = /* @__PURE__ */ __name((ghostNodes, viewableNodes, id2) => {
    try {
      const parentNode = ghostNodes.find((node) => node.id === id2);
      const parentNodeId = parentNode.ancestors()[1].id;
      const isPresentInOldNodes = viewableNodes.some(
        (oldNode) => oldNode.id === parentNodeId
      );
      if (isPresentInOldNodes) {
        return parentNode.ancestors()[1];
      } else {
        return getFirstDisplayedAncestor(ghostNodes, viewableNodes, parentNodeId);
      }
    } catch (e) {
      return ghostNodes.find((node) => node.id === id2);
    }
  }, "getFirstDisplayedAncestor");
  var setNodeLocation = /* @__PURE__ */ __name((xPosition, yPosition, settings) => {
    if (settings.isHorizontal) {
      return "translate(" + yPosition + "," + xPosition + ")";
    } else {
      return "translate(" + xPosition + "," + yPosition + ")";
    }
  }, "setNodeLocation");
  var RefreshQueue = class {
    static {
      __name(this, "RefreshQueue");
    }
    // The queue is an array that contains objects. Each object represents an
    // refresh action and only they have 2 properties:
    // {
    //     callback:          triggers when it's the first of queue and then it
    //                        becomes null to prevent that callback executes more
    //                        than once.
    //     delayNextCallback: when callback is executed, queue will subtracts
    //                        milliseconds from it. When it becomes 0, the entire
    //                        object is destroyed (shifted) from the array and then
    //                        the next item (if exists) will be executed similary
    //                        to this.
    // }
    static queue = [];
    // Contains setInterval ID
    static runner;
    // Milliseconds of each iteration
    static runnerSpeed = 100;
    // Developer internal magic number. Time added at end of refresh transition to
    // let DOM and d3 rest before another refresh.
    // 0 creates console and visual errors because getFirstDisplayedAncestor never
    // found the needed id and setNodeLocation receives undefined parameters.
    // Between 50 and 100 milliseconds seems enough for 10 nodes (demo example)
    static extraDelayBetweenCallbacks = 100;
    // Developer internal for debugging RefreshQueue class. Set true to see
    // console "real time" queue of tasks.
    // If there is a cleaner method, remove it!
    static showQueueLog = false;
    // Adds one refresh action to the queue. When safe callback will be
    // triggered
    static add(duration, callback) {
      this.queue.push({
        delayNextCallback: duration + this.extraDelayBetweenCallbacks,
        callback
      });
      this.log(
        this.queue.map((_) => _.delayNextCallback),
        "<-- New task !!!"
      );
      if (!this.runner) {
        this.runnerFunction();
        this.runner = setInterval(() => this.runnerFunction(), this.runnerSpeed);
      }
    }
    // Each this.runnerSpeed milliseconds it's executed. It stops when finish.
    static runnerFunction() {
      if (this.queue[0]) {
        if (this.queue[0].callback) {
          this.log("Executing task, delaying next task...");
          try {
            this.queue[0].callback();
          } catch (e) {
            console.error(e);
          } finally {
            this.queue[0].callback = null;
          }
        }
        this.queue[0].delayNextCallback -= this.runnerSpeed;
        this.log(this.queue.map((_) => _.delayNextCallback));
        if (this.queue[0].delayNextCallback <= 0) {
          this.queue.shift();
        }
      } else {
        this.log("No task found");
        clearInterval(this.runner);
        this.runner = 0;
      }
    }
    // Print to console debug data if this.showQueueLog = true
    static log(...msg) {
      if (this.showQueueLog) console.log(...msg);
    }
  };

  // src/initializeSVG.ts
  var initiliazeSVG = /* @__PURE__ */ __name((treeConfig) => {
    const {
      htmlId,
      isHorizontal,
      hasPan,
      hasZoom,
      mainAxisNodeSpacing,
      nodeHeight,
      nodeWidth,
      marginBottom,
      marginLeft,
      marginRight,
      marginTop
    } = treeConfig;
    const margin = {
      top: marginTop,
      right: marginRight,
      bottom: marginBottom,
      left: marginLeft
    };
    const { areaHeight, areaWidth } = getAreaSize(treeConfig.htmlId);
    const width = areaWidth - margin.left - margin.right;
    const height = areaHeight - margin.top - margin.bottom;
    const svg = d3_default.select("#" + htmlId).append("svg").attr("width", areaWidth).attr("height", areaHeight);
    const ZoomContainer = svg.append("g");
    const zoom = d3_default.zoom().on("zoom", (e) => {
      ZoomContainer.attr("transform", () => e.transform);
    });
    svg.call(zoom);
    if (!hasPan) {
      svg.on("mousedown.zoom", null).on("touchstart.zoom", null).on("touchmove.zoom", null).on("touchend.zoom", null);
    }
    if (!hasZoom) {
      svg.on("wheel.zoom", null).on("mousewheel.zoom", null).on("mousemove.zoom", null).on("DOMMouseScroll.zoom", null).on("dblclick.zoom", null);
    }
    const MainG = ZoomContainer.append("g").attr(
      "transform",
      mainAxisNodeSpacing === "auto" ? "translate(0,0)" : isHorizontal ? "translate(" + margin.left + "," + (margin.top + height / 2 - nodeHeight / 2) + ")" : "translate(" + (margin.left + width / 2 - nodeWidth / 2) + "," + margin.top + ")"
    );
    return MainG;
  }, "initiliazeSVG");

  // src/links/draw-links.ts
  var generateLinkLayout = /* @__PURE__ */ __name((s, d, treeConfig) => {
    const { isHorizontal, nodeHeight, nodeWidth, linkShape } = treeConfig;
    if (linkShape === "orthogonal") {
      if (isHorizontal) {
        return `M ${s.y} ${s.x + nodeHeight / 2}
        L ${(s.y + d.y + nodeWidth) / 2} ${s.x + nodeHeight / 2}
        L  ${(s.y + d.y + nodeWidth) / 2} ${d.x + nodeHeight / 2}
          ${d.y + nodeWidth} ${d.x + nodeHeight / 2}`;
      } else {
        return `M ${s.x + nodeWidth / 2} ${s.y}
        L ${s.x + nodeWidth / 2} ${(s.y + d.y + nodeHeight) / 2}
        L  ${d.x + nodeWidth / 2} ${(s.y + d.y + nodeHeight) / 2}
          ${d.x + nodeWidth / 2} ${d.y + nodeHeight} `;
      }
    } else if (linkShape === "curve") {
      if (isHorizontal) {
        return `M ${s.y} ${s.x + nodeHeight / 2}
      L ${s.y - (s.y - d.y - nodeWidth) / 2 + 15} ${s.x + nodeHeight / 2}
      Q${s.y - (s.y - d.y - nodeWidth) / 2} ${s.x + nodeHeight / 2}
       ${s.y - (s.y - d.y - nodeWidth) / 2} ${s.x + nodeHeight / 2 - offsetPosOrNeg(s.x, d.x, 15)}
      L ${s.y - (s.y - d.y - nodeWidth) / 2} ${d.x + nodeHeight / 2}
      L ${d.y + nodeWidth} ${d.x + nodeHeight / 2}`;
      } else {
        return `M ${s.x + nodeWidth / 2} ${s.y}
      L ${s.x + nodeWidth / 2} ${s.y - (s.y - d.y - nodeHeight) / 2 + 15}
      Q${s.x + nodeWidth / 2} ${s.y - (s.y - d.y - nodeHeight) / 2}
      ${s.x + nodeWidth / 2 - offsetPosOrNeg(s.x, d.x, 15)} ${s.y - (s.y - d.y - nodeHeight) / 2}
      L ${d.x + nodeWidth / 2} ${s.y - (s.y - d.y - nodeHeight) / 2} 
      L ${d.x + nodeWidth / 2} ${d.y + nodeHeight} `;
      }
    } else {
      if (isHorizontal) {
        return `M ${s.y} ${s.x + nodeHeight / 2}
        C ${(s.y + d.y + nodeWidth) / 2} ${s.x + nodeHeight / 2}
          ${(s.y + d.y + nodeWidth) / 2} ${d.x + nodeHeight / 2}
          ${d.y + nodeWidth} ${d.x + nodeHeight / 2}`;
      } else {
        return `M ${s.x + nodeWidth / 2} ${s.y}
        C ${s.x + nodeWidth / 2} ${(s.y + d.y + nodeHeight) / 2}
          ${d.x + nodeWidth / 2} ${(s.y + d.y + nodeHeight) / 2}
          ${d.x + nodeWidth / 2} ${d.y + nodeHeight} `;
      }
    }
  }, "generateLinkLayout");
  var offsetPosOrNeg = /* @__PURE__ */ __name((val1, val2, offset) => val1 > val2 ? offset : val1 < val2 ? -offset : 0, "offsetPosOrNeg");

  // src/links/link-enter.ts
  var drawLinkEnter = /* @__PURE__ */ __name((link, settings, nodes, oldNodes) => link.enter().insert("path", "g").attr("class", "link").attr("d", (d) => {
    const firstDisplayedParentNode = getFirstDisplayedAncestor(
      nodes,
      oldNodes,
      d.id
    );
    const o = {
      x: firstDisplayedParentNode.x0,
      y: firstDisplayedParentNode.y0
    };
    return generateLinkLayout(o, o, settings);
  }).attr("fill", "none").attr(
    "stroke-width",
    (d) => settings.linkWidth(d)
    // Pass the correct `d` object to linkWidth
  ).attr(
    "stroke",
    (d) => settings.linkColor(d)
    // Pass the correct `d` object to linkColor
  ), "drawLinkEnter");

  // src/links/link-exit.ts
  var drawLinkExit = /* @__PURE__ */ __name((link, settings, nodes, oldNodes) => {
    link.exit().transition().duration(settings.duration).style("opacity", 0).attr("d", (d) => {
      const firstDisplayedParentNode = getFirstDisplayedAncestor(
        oldNodes,
        nodes,
        d.id
      );
      const o = {
        x: firstDisplayedParentNode.x0,
        y: firstDisplayedParentNode.y0
      };
      return generateLinkLayout(o, o, settings);
    }).remove();
  }, "drawLinkExit");

  // src/links/link-update.ts
  var drawLinkUpdate = /* @__PURE__ */ __name((linkEnter, link, settings) => {
    const linkUpdate = linkEnter.merge(link);
    linkUpdate.transition().duration(settings.duration).attr("d", (d) => {
      return generateLinkLayout(d, d.parent, settings);
    }).attr("fill", "none").attr("stroke-width", (d) => {
      return settings.linkWidth(d);
    }).attr("stroke", (d) => {
      return settings.linkColor(d);
    });
  }, "drawLinkUpdate");

  // src/nodes/node-enter.ts
  var drawNodeEnter = /* @__PURE__ */ __name((node, settings, nodes, oldNodes) => {
    const nodeEnter = node.enter().append("g").attr("class", "node").attr("id", (d) => d?.id).attr("transform", (d) => {
      const firstDisplayedParentNode = getFirstDisplayedAncestor(
        nodes,
        oldNodes,
        d.id
      );
      return setNodeLocation(
        firstDisplayedParentNode.x0,
        firstDisplayedParentNode.y0,
        settings
      );
    });
    nodeEnter.append("foreignObject").attr("width", settings.nodeWidth).attr("height", settings.nodeHeight);
    return nodeEnter;
  }, "drawNodeEnter");

  // src/nodes/node-exit.ts
  var drawNodeExit = /* @__PURE__ */ __name((node, settings, nodes, oldNodes) => {
    const nodeExit = node.exit().transition().duration(settings.duration).style("opacity", 0).attr("transform", (d) => {
      const firstDisplayedParentNode = getFirstDisplayedAncestor(
        oldNodes,
        nodes,
        d.id
      );
      return setNodeLocation(
        firstDisplayedParentNode.x0,
        firstDisplayedParentNode.y0,
        settings
      );
    }).remove();
    nodeExit.select("rect").style("fill-opacity", 1e-6);
    nodeExit.select("circle").attr("r", 1e-6);
    nodeExit.select("text").style("fill-opacity", 1e-6);
  }, "drawNodeExit");

  // src/nodes/node-update.ts
  var drawNodeUpdate = /* @__PURE__ */ __name((nodeEnter, node, settings) => {
    const nodeUpdate = nodeEnter.merge(node);
    nodeUpdate.transition().duration(settings.duration).attr("transform", (d) => {
      return settings.isHorizontal ? "translate(" + d.y + "," + d.x + ")" : "translate(" + d.x + "," + d.y + ")";
    });
    nodeUpdate.select("foreignObject").attr("width", settings.nodeWidth).attr("height", settings.nodeHeight).style("overflow", "visible").on("click", (_, d) => settings.onNodeClick({ ...d, settings })).on("mouseenter", (_, d) => settings.onNodeMouseEnter({ ...d, settings })).on("mouseleave", (_, d) => settings.onNodeMouseLeave({ ...d, settings })).html((d) => settings.renderNode({ ...d, settings }));
  }, "drawNodeUpdate");

  // src/prepare-data.ts
  var generateNestedData = /* @__PURE__ */ __name((data, treeConfig) => {
    const { idKey, relationnalField, hasFlatData } = treeConfig;
    return hasFlatData ? d3_default.stratify().id((d) => d[idKey]).parentId((d) => d[relationnalField])(data) : d3_default.hierarchy(data, (d) => d[relationnalField]);
  }, "generateNestedData");
  var generateBasicTreemap = /* @__PURE__ */ __name((treeConfig) => {
    const { areaHeight, areaWidth } = getAreaSize(treeConfig.htmlId);
    return treeConfig.mainAxisNodeSpacing === "auto" && treeConfig.isHorizontal ? d3_default.tree().size([
      areaHeight - treeConfig.nodeHeight,
      areaWidth - treeConfig.nodeWidth
    ]) : treeConfig.mainAxisNodeSpacing === "auto" && !treeConfig.isHorizontal ? d3_default.tree().size([
      areaWidth - treeConfig.nodeWidth,
      areaHeight - treeConfig.nodeHeight
    ]) : treeConfig.isHorizontal === true ? d3_default.tree().nodeSize([
      treeConfig.nodeHeight * treeConfig.secondaryAxisNodeSpacing,
      treeConfig.nodeWidth
    ]) : d3_default.tree().nodeSize([
      treeConfig.nodeWidth * treeConfig.secondaryAxisNodeSpacing,
      treeConfig.nodeHeight
    ]);
  }, "generateBasicTreemap");

  // src/index.ts
  var Treeviz = {
    create: create2
  };
  if (typeof window !== "undefined") {
    window.Treeviz = Treeviz;
  }
  function create2(userSettings) {
    const defaultSettings = {
      data: [],
      htmlId: "",
      idKey: "id",
      relationnalField: "father",
      hasFlatData: true,
      nodeWidth: 160,
      nodeHeight: 100,
      mainAxisNodeSpacing: 300,
      renderNode: /* @__PURE__ */ __name(() => "Node", "renderNode"),
      linkColor: /* @__PURE__ */ __name(() => "#ffcc80", "linkColor"),
      linkWidth: /* @__PURE__ */ __name(() => 10, "linkWidth"),
      linkShape: "quadraticBeziers",
      isHorizontal: true,
      hasPan: false,
      hasZoom: false,
      duration: 600,
      onNodeClick: /* @__PURE__ */ __name(() => void 0, "onNodeClick"),
      onNodeMouseEnter: /* @__PURE__ */ __name(() => void 0, "onNodeMouseEnter"),
      onNodeMouseLeave: /* @__PURE__ */ __name(() => void 0, "onNodeMouseLeave"),
      marginBottom: 0,
      marginLeft: 0,
      marginRight: 0,
      marginTop: 0,
      secondaryAxisNodeSpacing: 1.25
    };
    let settings = {
      ...defaultSettings,
      ...userSettings
    };
    let oldNodes = [];
    function draw(svg2, computedTree) {
      const nodes = computedTree.descendants();
      const links = computedTree.descendants().slice(1);
      const { mainAxisNodeSpacing } = settings;
      if (mainAxisNodeSpacing !== "auto") {
        nodes.forEach((d) => {
          d.y = d.depth * settings.nodeWidth * mainAxisNodeSpacing;
        });
      }
      nodes.forEach((currentNode) => {
        const currentNodeOldPosition = oldNodes.find(
          (node2) => node2.id === currentNode.id
        );
        currentNode.x0 = currentNodeOldPosition ? currentNodeOldPosition.x0 : currentNode.x;
        currentNode.y0 = currentNodeOldPosition ? currentNodeOldPosition.y0 : currentNode.y;
      });
      const node = svg2.selectAll("g.node").data(nodes, (d) => {
        return d[settings.idKey];
      });
      const nodeEnter = drawNodeEnter(node, settings, nodes, oldNodes);
      drawNodeUpdate(nodeEnter, node, settings);
      drawNodeExit(node, settings, nodes, oldNodes);
      const link = svg2.selectAll("path.link").data(links, (d) => {
        return d.id;
      });
      const linkEnter = drawLinkEnter(link, settings, nodes, oldNodes);
      drawLinkUpdate(linkEnter, link, settings);
      drawLinkExit(link, settings, nodes, oldNodes);
      oldNodes = [...nodes];
    }
    __name(draw, "draw");
    let nodeMap = /* @__PURE__ */ new Map();
    function refresh(data, newSettings) {
      RefreshQueue.add(settings.duration, () => {
        if (newSettings) {
          settings = { ...settings, ...newSettings };
        }
        const nestedData = generateNestedData(data, settings);
        const treemap = generateBasicTreemap(settings);
        const computedTree = treemap(nestedData);
        const nodes = computedTree.descendants();
        const updatedNodes = [];
        nodes.forEach((node) => {
          if (node.id != void 0) {
            const existing = nodeMap.get(node.id);
            if (!existing || existing.x !== node.x || existing.y !== node.y) {
              updatedNodes.push(node);
            }
            nodeMap.set(node.id, node);
          }
        });
        if (svg) {
          draw(svg, computedTree);
        }
      });
    }
    __name(refresh, "refresh");
    function clean(keepConfig) {
      const myNode = keepConfig ? document.querySelector(`#${settings.htmlId} svg g`) : document.querySelector(`#${settings.htmlId}`);
      if (myNode) {
        while (myNode.firstChild) {
          myNode.removeChild(myNode.firstChild);
        }
      }
      oldNodes = [];
    }
    __name(clean, "clean");
    const treeObject = { refresh, clean };
    const svg = initiliazeSVG(settings);
    return treeObject;
  }
  __name(create2, "create");
  return __toCommonJS(index_exports);
})();
