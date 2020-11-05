# COPYRIGHT (C) 2020 Nicotine+ Team
# COPYRIGHT (C) 2016-2017 Michael Labouebe <gfarmerfr@free.fr>
# COPYRIGHT (C) 2008-2010 Quinox <quinox@users.sf.net>
# COPYRIGHT (C) 2006-2009 Daelstorm <daelstorm@gmail.com>
# COPYRIGHT (C) 2003-2004 Hyriand <hyriand@thegraveyard.org>
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import time
from gettext import gettext as _

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Gtk

from pynicotine import slskmessages
from pynicotine.gtkgui.dirchooser import save_file
from pynicotine.gtkgui.utils import append_line
from pynicotine.gtkgui.utils import humanize
from pynicotine.gtkgui.utils import human_speed
from pynicotine.gtkgui.utils import IconNotebook
from pynicotine.gtkgui.utils import InfoBar
from pynicotine.gtkgui.utils import initialise_columns
from pynicotine.gtkgui.utils import load_ui_elements
from pynicotine.gtkgui.utils import PopupMenu
from pynicotine.gtkgui.utils import update_widget_visuals
from pynicotine.logfacility import log


# User Info and User Browse Notebooks
class UserTabs(IconNotebook):

    def __init__(self, frame, subwindow, notebookraw, tab):

        self.frame = frame

        ui = frame.np.config.sections["ui"]

        IconNotebook.__init__(
            self,
            self.frame.images,
            angle=ui["labelinfo"],
            tabclosers=ui["tabclosers"],
            show_hilite_image=self.frame.np.config.sections["notifications"]["notification_tab_icons"],
            reorderable=ui["tab_reorderable"],
            show_status_image=ui["tab_status_icons"],
            notebookraw=notebookraw
        )

        self.popup_enable()

        self.subwindow = subwindow

        self.users = {}
        self.tab = tab

    def init_window(self, user):

        w = self.users[user] = self.subwindow(self, user)
        self.append_page(w.Main, user[:15], w.on_close)
        self.frame.np.queue.put(slskmessages.AddUser(user))

    def show_user(self, user, conn=None, msg=None):

        if user in self.users:
            self.users[user].conn = conn
        else:
            self.init_window(user)

        self.users[user].show_user(msg)
        self.request_changed(self.users[user].Main)

        if self.tab is not None:
            self.frame.request_tab_icon(self.tab)

        tab_name = self.frame.match_main_notebox(self.tab)
        self.frame.change_main_page(tab_name)

    def show_connection_error(self, user):
        self.users[user].show_connection_error()

    def save_columns(self):

        for user in self.users:
            self.users[user].save_columns()

    def get_user_stats(self, msg):

        if msg.user in self.users:
            tab = self.users[msg.user]
            tab.speed.set_text(_("Speed: %s") % human_speed(msg.avgspeed))
            tab.filesshared.set_text(_("Files: %s") % humanize(msg.files))
            tab.dirsshared.set_text(_("Directories: %s") % humanize(msg.dirs))

    def get_user_status(self, msg):

        if msg.user in self.users:

            tab = self.users[msg.user]
            tab.status = msg.status
            status = [_("Offline"), _("Away"), _("Online")][msg.status]

            if not self.frame.np.config.sections["ui"]["tab_status_icons"]:
                self.set_text(tab.Main, "%s (%s)" % (msg.user[:15], status))
            else:
                self.set_text(tab.Main, msg.user)

            self.set_status_image(tab.Main, msg.status)

    def show_interests(self, msg):

        if msg.user in self.users:
            self.users[msg.user].show_interests(msg.likes, msg.hates)

    def update_gauge(self, msg):

        for i in self.users.values():
            if i.conn == msg.conn.conn:
                i.update_gauge(msg)

    def update_visuals(self):

        for i in self.users.values():
            i.update_visuals()

    def tab_popup(self, user):

        popup = PopupMenu(self.frame)
        popup.setup(
            ("#" + _("Send _message"), popup.on_send_message),
            ("#" + _("Show IP a_ddress"), popup.on_show_ip_address),
            ("#" + _("Get user i_nfo"), popup.on_get_user_info),
            ("#" + _("Brow_se files"), popup.on_browse_user),
            ("#" + _("Gi_ve privileges"), popup.on_give_privileges),
            ("#" + _("Client Version"), popup.on_version),
            ("", None),
            ("$" + _("Add user to list"), popup.on_add_to_list),
            ("$" + _("Ban this user"), popup.on_ban_user),
            ("$" + _("Ignore this user"), popup.on_ignore_user),
            ("", None),
            ("#" + _("Close this tab"), self.users[user].on_close)
        )

        popup.set_user(user)

        items = popup.get_children()

        items[7].set_active(user in (i[0] for i in self.frame.np.config.sections["server"]["userlist"]))
        items[8].set_active(user in self.frame.np.config.sections["server"]["banlist"])
        items[9].set_active(user in self.frame.np.config.sections["server"]["ignorelist"])

        return popup

    def on_tab_click(self, widget, event, child):

        if event.type == Gdk.EventType.BUTTON_PRESS:

            n = self.page_num(child)
            page = self.get_nth_page(n)
            username = next(user for user, tab in self.users.items() if tab.Main is page)

            if event.button == 2:
                self.users[username].on_close(widget)
                return True

            if event.button == 3:
                menu = self.tab_popup(username)
                menu.popup(None, None, None, None, event.button, event.time)
                return True

            return False

        return False

    def conn_close(self):

        self.connected = 0

        for user in self.users:
            tab = self.users[user]
            tab.status = 0
            status = _("Offline")
            self.set_text(tab.Main, "%s (%s)" % (user[:15], status))


class UserInfo:

    def __init__(self, userinfos, user):

        # Build the window
        load_ui_elements(self, os.path.join(os.path.dirname(os.path.realpath(__file__)), "ui", "userinfo.ui"))

        self.userinfos = userinfos
        self.frame = userinfos.frame

        self.frame.np.queue.put(slskmessages.UserInterests(user))
        self.user = user
        self.conn = None
        self._descr = ""
        self.image_pixbuf = None
        self.zoom_factor = 5
        self.actual_zoom = 0
        self.status = 0

        self.hates_store = Gtk.ListStore(str)
        self.Hates.set_model(self.hates_store)

        cols = initialise_columns(self.Hates, [_("Hates"), 0, "text"])
        cols[0].set_sort_column_id(0)

        self.hates_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)

        self.likes_store = Gtk.ListStore(str)
        self.Likes.set_model(self.likes_store)

        cols = initialise_columns(self.Likes, [_("Likes"), 0, "text"])
        cols[0].set_sort_column_id(0)

        self.likes_store.set_sort_column_id(0, Gtk.SortType.ASCENDING)

        self.tag_local = self.descr.get_buffer().create_tag()

        self.update_visuals()

        self.likes_popup_menu = popup = PopupMenu(self.frame)
        popup.setup(
            ("$" + _("I _like this"), self.frame.interests.on_like_recommendation),
            ("$" + _("I _don't like this"), self.frame.interests.on_dislike_recommendation),
            ("", None),
            ("#" + _("_Search for this item"), self.frame.interests.on_recommend_search)
        )

        self.Likes.connect("button_press_event", self.on_popup_likes_menu)

        self.hates_popup_menu = popup = PopupMenu(self.frame)
        popup.setup(
            ("$" + _("I _like this"), self.frame.interests.on_like_recommendation),
            ("$" + _("I _don't like this"), self.frame.interests.on_dislike_recommendation),
            ("", None),
            ("#" + _("_Search for this item"), self.frame.interests.on_recommend_search)
        )

        self.Hates.connect("button_press_event", self.on_popup_hates_menu)

        self.image_menu = popup = PopupMenu(self.frame)
        popup.setup(
            ("#" + _("Zoom 1:1"), self.make_zoom_normal),
            ("#" + _("Zoom In"), self.make_zoom_in),
            ("#" + _("Zoom Out"), self.make_zoom_out),
            ("", None),
            ("#" + _("Save Picture"), self.on_save_picture)
        )

    def on_popup_likes_menu(self, widget, event):

        if event.button != 3:
            return

        d = self.Likes.get_path_at_pos(int(event.x), int(event.y))
        if not d:
            return

        path, column, x, y = d

        iterator = self.likes_store.get_iter(path)
        thing = self.likes_store.get_value(iterator, 0)
        items = self.likes_popup_menu.get_children()

        self.likes_popup_menu.set_user(thing)

        items[0].set_active(thing in self.frame.np.config.sections["interests"]["likes"])
        items[1].set_active(thing in self.frame.np.config.sections["interests"]["dislikes"])

        self.likes_popup_menu.popup(None, None, None, None, event.button, event.time)

    def on_popup_hates_menu(self, widget, event):

        if event.button != 3:
            return

        d = self.Hates.get_path_at_pos(int(event.x), int(event.y))
        if not d:
            return

        path, column, x, y = d

        iterator = self.hates_store.get_iter(path)
        thing = self.hates_store.get_value(iterator, 0)
        items = self.hates_popup_menu.get_children()

        self.hates_popup_menu.set_user(thing)

        items[0].set_active(thing in self.frame.np.config.sections["interests"]["likes"])
        items[1].set_active(thing in self.frame.np.config.sections["interests"]["dislikes"])

        self.hates_popup_menu.popup(None, None, None, None, event.button, event.time)

    def update_visuals(self):

        for widget in self.__dict__.values():
            update_widget_visuals(widget)

    def show_interests(self, likes, hates):

        self.likes_store.clear()
        self.hates_store.clear()

        for like in likes:
            self.likes_store.append([like])

        for hate in hates:
            self.hates_store.append([hate])

    def show_user(self, msg):

        if msg is None:
            return

        self.conn = None
        self._descr = msg.descr
        self.image_pixbuf = None
        self.descr.get_buffer().set_text("")

        append_line(self.descr, msg.descr, self.tag_local, showstamp=False, scroll=False)

        self.uploads.set_text(_("Total uploads allowed: %i") % msg.totalupl)
        self.queuesize.set_text(_("Queue size: %i") % msg.queuesize)

        if msg.slotsavail:
            slots = _("Yes")
        else:
            slots = _("No")

        self.slotsavail.set_text(_("Slots free: %s") % slots)

        if msg.uploadallowed == 0:
            allowed = _("No one")
        elif msg.uploadallowed == 1:
            allowed = _("Everyone")
        elif msg.uploadallowed == 2:
            allowed = _("Users in list")
        elif msg.uploadallowed == 3:
            allowed = _("Trusted Users")
        else:
            allowed = _("unknown")

        self.AcceptUploads.set_text(_("%s") % allowed)

        if msg.has_pic and msg.pic is not None:
            try:
                import gc
                loader = GdkPixbuf.PixbufLoader()
                loader.write(msg.pic)
                loader.close()
                self.image_pixbuf = loader.get_pixbuf()
                self.image.set_from_pixbuf(self.image_pixbuf)
                del msg.pic, loader
                gc.collect()
                self.actual_zoom = 0
                self.SavePicture.set_sensitive(True)
            except TypeError:
                import tempfile
                name = tempfile.NamedTemporaryFile(delete=False)
                with open(name, "w") as f:
                    f.write(msg.pic)

                self.image.set_from_file(name)
                os.remove(name)

    def show_connection_error(self):

        InfoBar(self.InfoBar, Gtk.MessageType.INFO).show_message(
            _("Unable to request information from user. Either you both have a closed listening port, the user is offline, or there's a temporary connectivity issue.")
        )

    def update_gauge(self, msg):

        if msg.total == 0 or msg.bytes == 0:
            fraction = 0.0
        elif msg.bytes >= msg.total:
            fraction = 1.0
        else:
            fraction = float(msg.bytes) / msg.total

        self.progressbar.set_fraction(fraction)

    """ Events """

    def on_send_message(self, widget):
        self.frame.privatechats.send_message(self.user, show_user=True)
        self.frame.change_main_page("private")

    def on_show_ip_address(self, widget):

        self.frame.np.ip_requested.add(self.user)
        self.frame.np.queue.put(slskmessages.GetPeerAddress(self.user))

    def on_refresh(self, widget):
        self.frame.local_user_info_request(self.user)

    def on_browse_user(self, widget):
        self.frame.browse_user(self.user)

    def on_add_to_list(self, widget):
        self.frame.np.userlist.add_to_list(self.user)

    def on_ban_user(self, widget):
        self.frame.ban_user(self.user)

    def on_ignore_user(self, widget):
        self.frame.ignore_user(self.user)

    def on_close(self, widget):

        del self.userinfos.users[self.user]

        self.userinfos.remove_page(self.Main)
        self.Main.destroy()

    def on_save_picture(self, widget):

        if self.image is None or self.image_pixbuf is None:
            return

        response = save_file(
            self.frame.MainWindow,
            self.frame.np.config.sections["transfers"]["downloaddir"],
            "%s %s.jpg" % (self.user, time.strftime("%Y-%m-%d %H_%M_%S")),
            title="Save as..."
        )

        if not response:
            return

        pathname = response[0]

        if not os.path.exists(pathname):
            self.image_pixbuf.savev(pathname, "jpeg", ["quality"], ["100"])
            log.add(_("Picture saved to %s"), pathname)
        else:
            log.add(_("Picture not saved, %s already exists."), pathname)

    def on_image_click(self, widget, event):

        if event.type != Gdk.EventType.BUTTON_PRESS or event.button != 3:
            return False

        act = True

        if self.image is None or self.image_pixbuf is None:
            act = False

        items = self.image_menu.get_children()
        for item in items:
            item.set_sensitive(act)

        self.image_menu.popup(None, None, None, None, event.button, event.time)

        return True  # Don't scroll the Gtk.ScrolledWindow

    def on_scroll_event(self, widget, event):

        if event.get_scroll_deltas().delta_y < 0:
            self.make_zoom_in()
        else:
            self.make_zoom_out()

        return True  # Don't scroll the Gtk.ScrolledWindow

    def make_zoom_normal(self, widget):
        self.make_zoom_in(zoom=True)

    def make_zoom_in(self, widget=None, zoom=None):

        def calc_zoom_in(a):
            return a + a * self.actual_zoom / 100 + a * self.zoom_factor / 100

        import gc

        if self.image is None or self.image_pixbuf is None or self.actual_zoom > 100:
            return

        x = self.image_pixbuf.get_width()
        y = self.image_pixbuf.get_height()

        if zoom:
            self.actual_zoom = 0
        else:
            self.actual_zoom += self.zoom_factor

        pixbuf_zoomed = self.image_pixbuf.scale_simple(calc_zoom_in(x), calc_zoom_in(y), GdkPixbuf.InterpType.TILES)
        self.image.set_from_pixbuf(pixbuf_zoomed)

        del pixbuf_zoomed

        gc.collect()

    def make_zoom_out(self, widget=None):

        def calc_zoom_out(a):
            return a + a * self.actual_zoom / 100 - a * self.zoom_factor / 100

        import gc

        if self.image is None or self.image_pixbuf is None:
            return

        x = self.image_pixbuf.get_width()
        y = self.image_pixbuf.get_height()

        self.actual_zoom -= self.zoom_factor

        if calc_zoom_out(x) < 10 or calc_zoom_out(y) < 10:
            self.actual_zoom += self.zoom_factor
            return

        pixbuf_zoomed = self.image_pixbuf.scale_simple(calc_zoom_out(x), calc_zoom_out(y), GdkPixbuf.InterpType.TILES)
        self.image.set_from_pixbuf(pixbuf_zoomed)

        del pixbuf_zoomed

        gc.collect()
