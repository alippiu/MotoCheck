(() => {
    const locateButton = document.querySelector("[data-locate]");
    const status = document.querySelector("[data-status]");
    const results = document.querySelector("[data-results]");
    const mapFrame = document.querySelector("[data-map-frame]");
    const mapFallback = document.querySelector("[data-map-fallback]");
    const areaForm = document.querySelector("[data-area-form]");
    if (!locateButton || !status || !results || !areaForm) return;

    let map;

    const setStatus = (message) => {
        status.textContent = message;
    };

    const distanceInKm = (fromLat, fromLon, toLat, toLon) => {
        const toRadians = (degrees) => (degrees * Math.PI) / 180;
        const latitudeDelta = toRadians(toLat - fromLat);
        const longitudeDelta = toRadians(toLon - fromLon);
        const haversine =
            Math.sin(latitudeDelta / 2) ** 2 +
            Math.cos(toRadians(fromLat)) *
                Math.cos(toRadians(toLat)) *
                Math.sin(longitudeDelta / 2) ** 2;
        return 6371 * 2 * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
    };

    const addLink = (container, label, href) => {
        if (!href) return;
        let protocol;
        try {
            protocol = new URL(href, window.location.href).protocol;
        } catch {
            return;
        }
        if (!["http:", "https:", "tel:"].includes(protocol)) return;
        if (protocol === "tel:" && !/^tel:[+\d().\-\s]{3,30}$/i.test(href)) return;
        const link = document.createElement("a");
        link.href = href;
        link.textContent = label;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        container.append(link);
    };

    const renderWorkshops = (workshops, latitude, longitude) => {
        results.replaceChildren();
        workshops.forEach((workshop) => {
            const card = document.createElement("article");
            card.className = "workshop-result";

            const title = document.createElement("h3");
            title.textContent = workshop.name || "Nama tidak tercatat di OpenStreetMap";
            card.append(title);

            const address = document.createElement("p");
            address.textContent = workshop.address || "Alamat tidak tercatat di OpenStreetMap.";
            card.append(address);

            const distance = document.createElement("p");
            const distanceKm = distanceInKm(
                latitude,
                longitude,
                workshop.latitude,
                workshop.longitude,
            );
            distance.textContent = `Sekitar ${distanceKm.toFixed(1)} km garis lurus`;
            card.append(distance);

            const actions = document.createElement("div");
            actions.className = "workshop-links";
            const directions = new URL("https://www.google.com/maps/dir/");
            directions.searchParams.set(
                "api",
                "1",
            );
            directions.searchParams.set(
                "destination",
                `${workshop.latitude},${workshop.longitude}`,
            );
            addLink(actions, "Petunjuk arah ↗", directions.href);
            addLink(actions, "Objek OpenStreetMap ↗", workshop.osm_url);
            addLink(actions, "Telepon", workshop.phone ? `tel:${workshop.phone}` : "");
            addLink(actions, "Situs web ↗", workshop.website);
            card.append(actions);
            results.append(card);
        });
    };

    const showMap = (workshops, latitude, longitude) => {
        mapFrame.hidden = false;
        if (!window.L) {
            mapFallback.hidden = false;
            return;
        }

        if (map) map.remove();
        map = window.L.map("workshop-map").setView([latitude, longitude], 13);
        window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
            maxZoom: 19,
            attribution:
                '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        }).addTo(map);
        window.L.marker([latitude, longitude])
            .addTo(map)
            .bindPopup("Lokasi pencarian");

        workshops.forEach((workshop) => {
            const marker = window.L.marker([workshop.latitude, workshop.longitude]).addTo(map);
            const popup = document.createElement("span");
            popup.textContent = workshop.name || "Nama tidak tercatat di OpenStreetMap";
            marker.bindPopup(popup);
        });
        window.setTimeout(() => map.invalidateSize(), 0);
    };

    const searchNearby = async (position) => {
        const latitude = position.coords.latitude;
        const longitude = position.coords.longitude;
        setStatus("Menghubungi OpenStreetMap untuk mencari tempat yang terpetakan…");
        results.replaceChildren();
        locateButton.disabled = true;
        try {
            const response = await fetch("/api/bengkel", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ latitude, longitude }),
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || "Pencarian bengkel gagal.");

            showMap(data.workshops, latitude, longitude);
            renderWorkshops(data.workshops, latitude, longitude);
            if (data.workshops.length) {
                setStatus(
                    `Menampilkan ${data.workshops.length} tempat terpetakan dalam radius 5 km. Jarak yang ditampilkan adalah garis lurus.`,
                );
            } else {
                setStatus("Tidak ada tempat dengan data bengkel motor yang ditemukan di radius ini. Data OSM mungkin belum lengkap.");
                addAreaFallback(latitude, longitude);
            }
        } catch (error) {
            setStatus(`${error.message} Kamu dapat mencoba pencarian area di bawah.`);
            addAreaFallback(latitude, longitude);
        } finally {
            locateButton.disabled = false;
        }
    };

    const addAreaFallback = (latitude, longitude) => {
        const link = document.createElement("a");
        const search = new URL("https://www.google.com/maps/search/");
        search.searchParams.set("api", "1");
        search.searchParams.set("query", `${latitude},${longitude} bengkel motor`);
        link.href = search.href;
        link.textContent = "Cari bengkel di Google Maps ↗";
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.className = "text-link";
        results.append(link);
    };

    locateButton.addEventListener("click", () => {
        if (!navigator.geolocation) {
            setStatus("Browser ini tidak mendukung lokasi. Gunakan pencarian kota atau area.");
            return;
        }
        locateButton.disabled = true;
        setStatus("Menunggu izin lokasi dari browser…");
        navigator.geolocation.getCurrentPosition(
            (position) => searchNearby(position),
            (error) => {
                locateButton.disabled = false;
                const message =
                    error.code === error.PERMISSION_DENIED
                        ? "Izin lokasi tidak diberikan."
                        : error.code === error.TIMEOUT
                          ? "Permintaan lokasi melewati batas waktu."
                          : "Lokasi tidak dapat diperoleh.";
                setStatus(`${message} Kamu tetap dapat mencari berdasarkan area.`);
            },
            { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 },
        );
    });

    areaForm.addEventListener("submit", (event) => {
        event.preventDefault();
        const areaInput = areaForm.elements.area;
        const area = areaInput.value.trim();
        if (!area) {
            setStatus("Masukkan nama kota atau area untuk mencari di Google Maps.");
            areaInput.focus();
            return;
        }
        if (area.length > 100) {
            setStatus("Nama kota atau area maksimal 100 karakter.");
            areaInput.focus();
            return;
        }
        const search = new URL("https://www.google.com/maps/search/");
        search.searchParams.set("api", "1");
        search.searchParams.set("query", `bengkel motor ${area}`);
        window.open(search.href, "_blank", "noopener,noreferrer");
    });
})();
