#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
**Project Name:**      MakeHuman

**Product Home Page:** http://www.makehumancommunity.org/

**Github Code Home Page:**    https://github.com/makehumancommunity/

**Authors:**           Glynn Clements

**Copyright(c):**      MakeHuman Team 2001-2020

**Licensing:**         AGPL3

    This file is part of MakeHuman Community (www.makehumancommunity.org).

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.


Abstract
--------

Python compatibility layer replacing the old C functions of MakeHuman.
"""

from core import G
from getpath import getPath, getDataPath, getSysDataPath, getSysPath, getRelativePath
from makehuman import getVersion, getVersionStr, getBasemeshVersion, getShortVersion, isRelease, isBuild, getVersionDigitsStr, getCopyrightMessage, getAssetLicense, getThirdPartyLicenses, getSoftwareLicense, getCredits

import os

_VULKAN = os.environ.get("MAKEHUMANO_VULKAN_PILOT") == "1"


def _backend_nao_disponivel(*args, **kwargs):
    raise RuntimeError("Canvas Vulkan do MakeHuman ainda não foi inicializado")


if _VULKAN:
    # Não importar glmodule ou classes OpenGL enquanto Vulkan está ativo.
    _grabScreenOpenGL = _backend_nao_disponivel
    _getPickedColorOpenGL = _backend_nao_disponivel
    _renderSkinOpenGL = _backend_nao_disponivel
    _renderToBufferOpenGL = _backend_nao_disponivel
    _renderAlphaMaskOpenGL = _backend_nao_disponivel
    _hasRenderSkinOpenGL = lambda: False
    _hasRenderToRenderbufferOpenGL = lambda: False
else:
    from glmodule import (
        grabScreen as _grabScreenOpenGL,
        getPickedColor as _getPickedColorOpenGL,
        hasRenderSkin as _hasRenderSkinOpenGL,
        renderSkin as _renderSkinOpenGL,
        hasRenderToRenderbuffer as _hasRenderToRenderbufferOpenGL,
        renderToBuffer as _renderToBufferOpenGL,
        renderAlphaMask as _renderAlphaMaskOpenGL,
    )


def _canvas_vulkan():
    canvas = getattr(G, "canvas", None)
    if canvas is not None and callable(getattr(canvas, "renderToBuffer", None)):
        return canvas
    return None


def hasRenderToRenderbuffer():
    """Vulkan usa textura offscreen; fora do piloto preserva implementação antiga."""
    if _canvas_vulkan() is not None:
        return True
    return _hasRenderToRenderbufferOpenGL()


def renderToBuffer(width, height, productionRender=True):
    canvas = _canvas_vulkan()
    if canvas is not None:
        return canvas.renderToBuffer(width, height, productionRender)
    return _renderToBufferOpenGL(width, height, productionRender)


def renderAlphaMask(width, height, productionRender=True):
    canvas = _canvas_vulkan()
    if canvas is not None:
        return canvas.renderAlphaMask(width, height, productionRender)
    return _renderAlphaMaskOpenGL(width, height, productionRender)


def hasRenderSkin():
    # renderSkin envolve geometria UV arbitrária e ainda não foi migrado.
    if _canvas_vulkan() is not None:
        return False
    return _hasRenderSkinOpenGL()


def renderSkin(*args, **kwargs):
    if _canvas_vulkan() is not None:
        raise NotImplementedError("renderSkin ainda precisa ser portado para Vulkan")
    return _renderSkinOpenGL(*args, **kwargs)


def grabScreen(x, y, width, height, filename=None, productionRender=False):
    """Captura a viewport Vulkan ativa ou mantém o caminho legado OpenGL."""
    canvas = getattr(G, "canvas", None)
    captura = getattr(canvas, "grabScreen", None)
    if callable(captura):
        return captura(x, y, width, height, filename, productionRender)
    return _grabScreenOpenGL(x, y, width, height, filename, productionRender)


def getPickedColor(x=None, y=None):
    """Interface original de seleção, roteada para o canvas Vulkan piloto.

    A migração final substituirá as demais APIs do glmodule. Enquanto
    isso, esta função evita glReadPixels e os efeitos colaterais da
    picking buffer GL durante a interação na viewport Vulkan.
    """
    canvas = getattr(G, "canvas", None)
    if canvas is not None and hasattr(canvas, "getPickedColor"):
        return canvas.getPickedColor(x, y)
    return _getPickedColorOpenGL(x, y)

from image import Image
if _VULKAN:
    from vulkan_texture import Texture, getTexture, reloadTextures
    from vulkan_shader import Shader
else:
    from texture import Texture, getTexture, reloadTextures
    from shader import Shader
from camera import Camera, OrbitalCamera

from qtui import Keys, Buttons, Modifiers, Application
from qtui import callAsyncThread, setShortcut
from qtui import getSaveFileName, getOpenFileName, getExistingDirectory

from inifile import parseINI, formatINI

cameras = G.cameras

def setClearColor(r, g, b, a):
    G.clearColor = (r, g, b, a)

def setCaption(caption):
    G.app.mainwin.setWindowTitle(caption)

def changeCategory(category):
    G.app.mainwin.tabs.changeTab(category)

def changeTask(category, task):
    if not G.app.mainwin.tabs.findTab(category):
        return
    changeCategory(category)
    G.app.mainwin.tabs.findTab(category).child.changeTab(task)

def refreshLayout():
    G.app.mainwin.refreshLayout()

def addPanels():
    return G.app.mainwin.addPanels()

def showPanels(left, right):
    return G.app.mainwin.showPanels(left, right)

def addTopWidget(widget, *args, **kwargs):
    return G.app.mainwin.addTopWidget(widget, *args, **kwargs)

def removeTopWidget(widget):
    return G.app.mainwin.removeTopWidget(widget)

def addToolBar(name):
    return G.app.mainwin.addToolBar(name)

def redraw():
    G.app.redraw()

def getKeyModifiers():
    return int(G.app.keyboardModifiers())

def addTimer(milliseconds, callback):
    return G.app.addTimer(milliseconds, callback)

def removeTimer(id):
    G.app.removeTimer(id)

def callAsync(func, *args, **kwargs):
    G.app.callAsync(func, *args, **kwargs)

def getSetting(setting_name):
    return G.app.getSetting(setting_name)

def setSetting(setting_name, value):
    G.app.setSetting(setting_name, value)
