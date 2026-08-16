class RouteImpossibleError(Exception):
    """Raised when the current fuel range cannot reach any station or the destination.

    This refers only to the stations currently available to the optimizer (the
    successfully geocoded dataset), not to the real-world existence of stations.
    ``from_mile``/``to_mile`` bound the route segment, in miles from the route
    origin, in which no reachable geocoded station was found.
    """

    def __init__(self, from_mile: float, to_mile: float):
        self.from_mile = from_mile
        self.to_mile = to_mile
        super().__init__(
            "No reachable fuel station was found in the available geocoded "
            f"station dataset between mile {from_mile:.0f} and mile {to_mile:.0f}"
        )
