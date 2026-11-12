def view_state(state, name):
    for monitor in state.monitors:
        if monitor.name == name:
            view = state._replace(active=monitor.active, windows=monitor.windows, fullscreen=monitor.fullscreen)
            return view if monitor.occupied is None else view._replace(occupied=set(monitor.occupied))
    return state


class MonitorView:
    def __init__(self, wm, monitor):
        self._wm = wm
        self.monitor = monitor

    def subscribe(self, callback):
        last = []

        def deliver(state):
            view = view_state(state, self.monitor.name) if self.monitor is not None else state
            if last and last[0] == view:
                return
            last[:] = [view]
            callback(view)
        self._wm.subscribe(deliver)

    def goto(self, workspace_id):
        if self.monitor is not None and getattr(self._wm, "per_output_workspaces", False):
            self._wm.goto(workspace_id, self.monitor.name)
        else:
            self._wm.goto(workspace_id)

    def output_scale(self):
        return self.monitor.scale if self.monitor is not None else self._wm.output_scale()

    def apply_layer_rules(self):
        self._wm.apply_layer_rules()

    def monitors(self):
        return self._wm.monitors()

    def start(self):
        pass
