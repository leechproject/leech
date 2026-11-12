class NoDock:
    def pinned_count(self):
        return 0

    def current_size(self):
        return (0.0, 0.0)

    def final_size(self):
        return None

    def icon_infos(self):
        return []

    def extra_width(self):
        return 0

    def output_scale(self):
        return None

    def suspend(self, instant=True):
        pass

    def resume(self, instant=True):
        return False

    def try_pin(self, _app_id):
        return False, "док отключён в конфиге"

    def try_unpin(self, _app_id):
        return False, "док отключён в конфиге"


class DetachedDock(NoDock):
    def __init__(self, dock):
        self._dock = dock

    def pinned_count(self):
        return self._dock.pinned_count()

    def try_pin(self, app_id):
        return self._dock.try_pin(app_id)

    def try_unpin(self, app_id):
        return self._dock.try_unpin(app_id)


class NoNotch:
    def suppress(self, _on):
        pass


class NoNotifications:
    def notify_local(self, summary, body="", _icon_name="", critical=False):
        print(f"leech: {summary}: {body}" if body else f"leech: {summary}")

    def dismiss(self, _nid):
        pass
