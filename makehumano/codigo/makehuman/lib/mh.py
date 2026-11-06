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

from image import Image
from vulkan_texture import Texture, getTexture, reloadTextures
from vulkan_shader import Shader


def _canvas_vulkan():
    """Obtém o canvas definitivo do MakeHuman original."""
    canvas = getattr(G, "canvas", None)
    if canvas is None or not callable(getattr(canvas, "renderToBuffer", None)):
        raise RuntimeError("Canvas Vulkan do MakeHuman ainda não foi inicializado")
    return canvas


def hasRenderToRenderbuffer():
    """O backend Vulkan implementa framebuffers de resolução independente."""
    return True


def hasRenderSkin():
    """O backend Vulkan possui rasterização de malhas UV."""
    return True


def renderToBuffer(width, height, productionRender=True):
    return _canvas_vulkan().renderToBuffer(width, height, productionRender)


def renderAlphaMask(width, height, productionRender=True):
    return _canvas_vulkan().renderAlphaMask(width, height, productionRender)


def renderSkin(*args, **kwargs):
    return _canvas_vulkan().renderSkin(*args, **kwargs)


def grabScreen(x, y, width, height, filename=None, productionRender=False):
    return _canvas_vulkan().grabScreen(
        x, y, width, height, filename, productionRender,
    )


def getPickedColor(x=None, y=None):
    return _canvas_vulkan().getPickedColor(x, y)


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
