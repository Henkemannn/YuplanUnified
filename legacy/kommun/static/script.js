document.addEventListener("DOMContentLoaded", () => {
    // Hantera klick på cell
    document.querySelectorAll("td[data-kostid]").forEach(cell => {
        cell.addEventListener("click", () => {
            cell.classList.toggle("markerad");
            saveSingleCell(cell);
        });
    });

    // Hantera klick på veckodagsrubrik – gulmarkera lunchrutor i samma tabell
    document.querySelectorAll(".veckodag-header").forEach(header => {
        header.addEventListener("click", () => {
            const dag = header.dataset.dag;
            const table = header.closest("table");

            table.querySelectorAll(`td[data-dag='${dag}'][data-maltid='Lunch']`).forEach(cell => {
                cell.classList.toggle("gulmarkerad");
            });
        });
    });
});


function saveSingleCell(cell) {
    const markerad = cell.classList.contains("markerad");
    const data = {
        vecka: parseInt(cell.dataset.vecka),
        dag: cell.dataset.dag,
        maltid: cell.dataset.maltid,
        avdelning_id: parseInt(cell.dataset.avdelningId),
        kosttyp_id: parseInt(cell.dataset.kostid),
        markerad: markerad ? 1 : 0
    };
    fetch("/registrera_klick", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(data)
    });
}
