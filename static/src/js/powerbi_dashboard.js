/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";

class PowerBIDashboard extends Component {
    static template = xml`
        <iframe
            src="https://app.powerbi.com/reportEmbed?reportId=e4828efc-1807-4d96-b7e8-c72f7e25fec6&amp;autoAuth=true&amp;ctid=fc6a9568-3e3f-4641-a905-4a4dc6639291"
            style="width:100%; height:90vh; border:none;"
            allowfullscreen="true">
        </iframe>
    `;
}

registry.category("actions").add("powerbi_dashboard", PowerBIDashboard);