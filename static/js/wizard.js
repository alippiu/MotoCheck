(() => {
    const form = document.querySelector("[data-wizard]");
    if (!form) return;

    const steps = [...form.querySelectorAll("[data-step]")];
    const controls = form.querySelector("[data-wizard-controls]");
    const previousButton = form.querySelector("[data-previous]");
    const nextButton = form.querySelector("[data-next]");
    const submitButton = form.querySelector("[data-submit]");
    const progressLabel = form.querySelector("[data-progress-label]");
    const progressBar = form.querySelector("[data-progress-bar]");
    const symptomCount = form.querySelector("[data-symptom-count]");
    const symptomSearch = form.querySelector("[data-symptom-search]");
    const symptomSearchEmpty = form.querySelector("[data-symptom-search-empty]");
    const primarySymptomSelect = form.querySelector("#primary-symptom");
    const brandSelect = form.querySelector("#brand");
    const modelSelect = form.querySelector("#model");
    const modelCustom = form.querySelector("#model-custom");
    const modelCustomLabel = form.querySelector("[data-model-custom-label]");
    const variantSelect = form.querySelector("#variant");
    const variantCustom = form.querySelector("#variant-custom");
    const variantCustomLabel = form.querySelector("[data-variant-custom-label]");
    const modelStatus = form.querySelector("[data-model-status]");
    const yearStatus = form.querySelector("[data-year-status]");
    const yearInput = form.querySelector("#year");
    const initialYear = yearInput.value;
    const configurationSelects = [
        "category",
        "transmission",
        "fuel_system",
        "cooling_system",
        "final_drive",
        "brakes",
        "front_brake",
        "rear_brake",
    ]
        .map((field) => form.querySelector(`#${field}`))
        .filter(Boolean);
    let activeStep = 0;

    const selectedSymptoms = () =>
        [...form.querySelectorAll('input[name="symptoms"]:checked')].map((input) => input.value);

    const updatePrimarySymptom = () => {
        const checkedInputs = [...form.querySelectorAll('input[name="symptoms"]:checked')];
        const selected = checkedInputs.map((input) => input.value);
        const preferred = primarySymptomSelect.value || primarySymptomSelect.dataset.initialPrimary;
        primarySymptomSelect.replaceChildren(
            new Option("Pilih gejala utama dari gejala yang dicentang", ""),
            ...checkedInputs.map(
                (input) =>
                    new Option(
                        input.closest(".symptom-option").querySelector(".symptom-name").textContent,
                        input.value,
                    ),
            ),
        );
        primarySymptomSelect.value = selected.includes(preferred)
            ? preferred
            : selected[0] || "";
        primarySymptomSelect.disabled = selected.length === 0;
        delete primarySymptomSelect.dataset.initialPrimary;
    };

    const updateModelOptions = () => {
        [...modelSelect.options].forEach((option) => {
            const available = !option.dataset.brand || option.dataset.brand === brandSelect.value;
            option.hidden = !available;
            option.disabled = !available;
        });
        if (modelSelect.selectedOptions[0]?.disabled) modelSelect.value = "";
    };

    const updateVariantOptions = () => {
        [...variantSelect.options].forEach((option) => {
            const available =
                !option.dataset.model || option.dataset.model === modelSelect.value;
            option.hidden = !available;
            option.disabled = !available;
        });
        if (variantSelect.selectedOptions[0]?.disabled) variantSelect.value = "";
        variantSelect.disabled = !modelSelect.value;
        variantSelect.required = Boolean(modelSelect.selectedOptions[0]?.dataset.brand);
        const isCustomModel = modelSelect.value === "other";
        const isCustomVariant = variantSelect.value === "other";
        modelCustom.hidden = !isCustomModel;
        modelCustomLabel.hidden = !isCustomModel;
        variantCustom.hidden = !isCustomVariant;
        variantCustomLabel.hidden = !isCustomVariant;
        applyVerifiedConfiguration();
    };

    const applyVerifiedConfiguration = () => {
        configurationSelects.forEach((select) => {
            if (select.dataset.verified === "true") {
                select.disabled = false;
                select.value = select.dataset.initialValue;
                delete select.dataset.verified;
            }
        });

        const option = variantSelect.selectedOptions[0];
        const configuration = JSON.parse(option?.dataset.configuration || "{}");
        if (yearInput.dataset.verified === "true") {
            yearInput.value = initialYear;
            yearInput.readOnly = false;
            delete yearInput.dataset.verified;
        }
        if (option?.dataset.year) {
            yearInput.value = option.dataset.year;
            yearInput.readOnly = true;
            yearInput.dataset.verified = "true";
        }
        if (yearStatus) {
            yearStatus.textContent = option?.dataset.year
                ? `Tahun ${option.dataset.year} tercantum pada portal Honda MotoPub. Isi manual belum ditinjau untuk memverifikasi konfigurasi.`
                : "Tahun model belum tersedia dari halaman resmi yang dirujuk; tahun yang kamu isi tidak diverifikasi. Pilih Belum dikonfirmasi untuk konfigurasi yang tidak kamu ketahui.";
        }
        for (const [field, value] of Object.entries(configuration)) {
            const select = form.querySelector(`#${field}`);
            if (!select) continue;
            select.value = value;
            select.disabled = true;
            select.dataset.verified = "true";
        }

        if (!modelStatus) return;
        const verifiedFields = Object.keys(configuration);
        const verifiedModel = Boolean(modelSelect.selectedOptions[0]?.dataset.brand);
        const fieldLabels = {
            category: "kategori bodi",
            transmission: "transmisi",
            fuel_system: "sistem bahan bakar",
            cooling_system: "sistem pendinginan",
            final_drive: "penggerak akhir",
            brakes: "sistem pengereman",
            front_brake: "rem depan",
            rear_brake: "rem belakang",
        };
        if (!modelSelect.value) {
            modelStatus.textContent = "Pilih model dari katalog atau model lain. Isian konfigurasi tidak dianggap spesifikasi resmi.";
        } else if (verifiedModel && !variantSelect.value) {
            modelStatus.textContent = "Pilih varian untuk mengisi konfigurasi yang tercantum pada sumber resmi.";
        } else if (verifiedFields.length) {
            const labels = verifiedFields.map((field) => fieldLabels[field] || field);
            modelStatus.textContent = `Konfigurasi ${labels.join(", ")} mengikuti sumber resmi untuk varian yang dipilih.${option?.dataset.year ? ` Tahun ${option.dataset.year} juga tercantum pada portal resmi.` : " Tahun model belum dicantumkan."}`;
        } else {
            modelStatus.textContent = "Konfigurasi model atau varian ini belum tersedia dari sumber resmi. Cocokkan dengan buku pedoman dan pilih Belum dikonfirmasi bila ragu.";
        }
    };

    const updateQuestions = () => {
        const selected = selectedSymptoms();
        form.querySelectorAll("[data-question]").forEach((container) => {
            const select = container.querySelector("select");
            const relevantSymptoms = container.dataset.symptoms.split(",");
            const visible = relevantSymptoms.some((id) => selected.includes(id));
            container.hidden = !visible;
            select.disabled = !visible;
        });
    };

    const updateCount = () => {
        const count = selectedSymptoms().length;
        updatePrimarySymptom();
        symptomCount.textContent = count
            ? `${count} gejala dipilih${count > 10 ? " — pilih maksimal 10." : "."}`
            : "Belum ada gejala dipilih.";
        symptomCount.classList.toggle("field-error", count > 10);
    };

    const filterSymptoms = () => {
        if (!symptomSearch) return;
        const query = symptomSearch.value.trim().toLocaleLowerCase("id");
        let visibleCount = 0;
        form.querySelectorAll(".symptom-group").forEach((group) => {
            const groupName = group.querySelector("legend").textContent.toLocaleLowerCase("id");
            let groupVisibleCount = 0;
            group.querySelectorAll(".symptom-option").forEach((option) => {
                const searchableText = `${groupName} ${option.textContent}`.toLocaleLowerCase("id");
                const matches = !query || searchableText.includes(query);
                option.hidden = !matches;
                if (matches) groupVisibleCount += 1;
            });
            group.hidden = groupVisibleCount === 0;
            visibleCount += groupVisibleCount;
        });
        if (symptomSearchEmpty) symptomSearchEmpty.hidden = visibleCount > 0;
    };

    const validateActiveStep = () => {
        if (activeStep === 0) {
            const brand = form.querySelector("#brand");
            if (!brand.value) {
                brand.setCustomValidity("Pilih merek atau Merek lain / tidak tahu.");
                brand.reportValidity();
                brand.setCustomValidity("");
                brand.focus();
                return false;
            }
            if (!modelSelect.value || !modelSelect.checkValidity()) {
                modelSelect.setCustomValidity("Pilih model dari katalog atau pilih Model lain / tidak diketahui.");
                modelSelect.reportValidity();
                modelSelect.setCustomValidity("");
                modelSelect.focus();
                return false;
            }
            if (variantSelect.required && !variantSelect.checkValidity()) {
                variantSelect.setCustomValidity("Pilih varian yang tercantum atau Varian lain / tidak diketahui.");
                variantSelect.reportValidity();
                variantSelect.setCustomValidity("");
                variantSelect.focus();
                return false;
            }
            const year = form.querySelector("#year");
            if (year.value && !year.checkValidity()) {
                year.reportValidity();
                year.focus();
                return false;
            }
        }
        if (activeStep === 1) {
            const count = selectedSymptoms().length;
            if (count < 1 || count > 10) {
                symptomCount.classList.add("field-error");
                form.querySelector('input[name="symptoms"]').focus();
                return false;
            }
            if (!selectedSymptoms().includes(primarySymptomSelect.value)) {
                primarySymptomSelect.setCustomValidity("Pilih satu gejala utama dari gejala yang dicentang.");
                primarySymptomSelect.reportValidity();
                primarySymptomSelect.setCustomValidity("");
                primarySymptomSelect.focus();
                return false;
            }
        }
        return true;
    };

    const showStep = (index) => {
        activeStep = index;
        steps.forEach((step, stepIndex) => {
            step.hidden = stepIndex !== index;
            step.setAttribute("aria-hidden", String(stepIndex !== index));
        });
        previousButton.hidden = index === 0;
        nextButton.hidden = index === steps.length - 1;
        submitButton.hidden = index !== steps.length - 1;
        progressLabel.textContent = `TAHAP ${String(index + 1).padStart(2, "0")} / 03`;
        progressBar.style.width = `${((index + 1) / steps.length) * 100}%`;
        form.querySelectorAll("[data-progress-name]").forEach((label) => {
            label.classList.toggle("current", Number(label.dataset.progressName) === index);
            label.classList.toggle("complete", Number(label.dataset.progressName) < index);
        });
        const heading = steps[index].querySelector("h2");
        if (heading) heading.setAttribute("tabindex", "-1"), heading.focus();
    };

    controls.hidden = false;
    configurationSelects.forEach((select) => {
        select.dataset.initialValue = select.value;
    });
    yearInput.dataset.initialValue = initialYear;
    updateModelOptions();
    updateVariantOptions();
    updateQuestions();
    updateCount();
    showStep(0);

    brandSelect.addEventListener("change", () => {
        modelSelect.value = "";
        modelCustom.value = "";
        variantSelect.value = "";
        variantCustom.value = "";
        updateModelOptions();
        updateVariantOptions();
    });
    modelSelect.addEventListener("change", () => {
        variantSelect.value = "";
        variantCustom.value = "";
        updateVariantOptions();
    });
    variantSelect.addEventListener("change", updateVariantOptions);

    form.querySelectorAll('input[name="symptoms"]').forEach((input) => {
        input.addEventListener("change", () => {
            updateCount();
            updateQuestions();
        });
    });
    symptomSearch?.addEventListener("input", filterSymptoms);

    nextButton.addEventListener("click", () => {
        if (validateActiveStep()) showStep(Math.min(activeStep + 1, steps.length - 1));
    });
    previousButton.addEventListener("click", () => showStep(Math.max(activeStep - 1, 0)));
    form.addEventListener("submit", (event) => {
        if (!validateActiveStep()) event.preventDefault();
    });
})();
