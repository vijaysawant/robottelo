"""CLI tests for RH Cloud - Inventory, aka Insights Inventory Upload

:Requirement: RHCloud

:CaseAutomation: Automated

:CaseComponent: RHCloud

:Team: Phoenix-subscriptions

:CaseImportance: High

"""

from datetime import UTC, datetime
import time

import pytest
from wait_for import wait_for

from robottelo.config import robottelo_tmp_dir
from robottelo.utils.io import get_local_file_data, get_remote_report_checksum

inventory_sync_task = 'InventorySync::Async::InventoryFullSync'
generate_report_jobs = 'ForemanInventoryUpload::Async::GenerateAllReportsJob'


@pytest.mark.e2e
def test_positive_inventory_generate_upload_cli(
    rhcloud_manifest_org, rhcloud_registered_hosts, module_target_sat
):
    """Tests Insights inventory generation and upload via foreman-rake commands:
    https://github.com/theforeman/foreman_rh_cloud/blob/master/README.md

    :id: f2da9506-97d4-4d1c-b373-9f71a52b8ab8

    :customerscenario: true

    :steps:

        0. Create a VM and register to insights within org having manifest.
        1. Generate and upload report for all organizations
            # /usr/sbin/foreman-rake rh_cloud_inventory:report:generate_upload
        2. Generate and upload report for specific organization
            # export organization_id=1
            # /usr/sbin/foreman-rake rh_cloud_inventory:report:generate_upload
        3. Generate report for specific organization (don't upload)
            # export organization_id=1
            # export target=/var/lib/foreman/red_hat_inventory/generated_reports/
            # /usr/sbin/foreman-rake rh_cloud_inventory:report:generate
        4. Upload previously generated report
            (needs to be named 'report_for_#{organization_id}.tar.gz')
            # export organization_id=1
            # export target=/var/lib/foreman/red_hat_inventory/generated_reports/
            # /usr/sbin/foreman-rake rh_cloud_inventory:report:upload

    :expectedresults: Inventory is generated and uploaded to cloud.redhat.com.

    :BZ: 1957129, 1895953, 1956190

    :CaseAutomation: Automated
    """
    org = rhcloud_manifest_org
    cmd = f'organization_id={org.id} foreman-rake rh_cloud_inventory:report:generate_upload'
    upload_success_msg = f"Generated and uploaded inventory report for organization '{org.name}'"
    result = module_target_sat.execute(cmd)
    assert result.status == 0
    assert upload_success_msg in result.stdout

    local_report_path = robottelo_tmp_dir.joinpath(f'report_for_{org.id}.tar.xz')
    remote_report_path = (
        f'/var/lib/foreman/red_hat_inventory/uploads/done/report_for_{org.id}.tar.xz'
    )
    wait_for(
        lambda: module_target_sat.get(
            remote_path=str(remote_report_path), local_path=str(local_report_path)
        ),
        timeout=60,
        delay=15,
        silent_failure=True,
        handle_exception=True,
    )
    local_file_data = get_local_file_data(local_report_path)
    assert local_file_data['checksum'] == get_remote_report_checksum(module_target_sat, org.id)
    assert local_file_data['size'] > 0
    assert local_file_data['extractable']
    assert local_file_data['json_files_parsable']

    slices_in_metadata = set(local_file_data['metadata_counts'].keys())
    slices_in_tar = set(local_file_data['slices_counts'].keys())
    assert slices_in_metadata == slices_in_tar
    for slice_name, hosts_count in local_file_data['metadata_counts'].items():
        assert hosts_count == local_file_data['slices_counts'][slice_name]


@pytest.mark.e2e
@pytest.mark.pit_server
@pytest.mark.pit_client
def test_positive_inventory_recommendation_sync(
    rhcloud_manifest_org,
    rhcloud_registered_hosts,
    module_target_sat,
):
    """Tests Insights recommendation sync via foreman-rake commands:
    https://github.com/theforeman/foreman_rh_cloud/blob/master/README.md

    :id: 361af91d-1246-4308-9cc8-66beada7d651

    :steps:

        0. Create a VM and register to insights within org having manifest.
        1. Sync insights recommendation using following foreman-rake command.
            # /usr/sbin/foreman-rake rh_cloud_insights:sync

    :expectedresults: Insights recommendations are successfully synced for the host.

    :BZ: 1957186

    :CaseAutomation: Automated
    """
    org = rhcloud_manifest_org
    cmd = f'organization_id={org.id} foreman-rake rh_cloud_insights:sync'
    timestamp = datetime.now(UTC).strftime('%Y-%m-%d %H:%M')
    result = module_target_sat.execute(cmd)
    wait_for(
        lambda: module_target_sat.api.ForemanTask()
        .search(query={'search': f'Insights full sync and started_at >= "{timestamp}"'})[0]
        .result
        == 'success',
        timeout=400,
        delay=15,
        silent_failure=True,
        handle_exception=True,
    )
    assert result.status == 0
    assert result.stdout == 'Synchronized Insights hosts hits data\n'


@pytest.mark.e2e
@pytest.mark.pit_server
@pytest.mark.pit_client
def test_positive_sync_inventory_status(
    rhcloud_manifest_org,
    rhcloud_registered_hosts,
    module_target_sat,
):
    """Sync inventory status via foreman-rake commands:
    https://github.com/theforeman/foreman_rh_cloud/blob/master/README.md

    :id: 915ffbfd-c2e6-4296-9d69-f3f9a0e79b32

    :steps:

        0. Create a VM and register to insights within org having manifest.
        1. Sync inventory status for specific organization.
            # export organization_id=1
            # /usr/sbin/foreman-rake rh_cloud_inventory:sync

    :expectedresults: Inventory status is successfully synced for satellite hosts.

    :BZ: 1957186

    :CaseAutomation: Automated
    """
    org = rhcloud_manifest_org
    cmd = f'organization_id={org.id} foreman-rake rh_cloud_inventory:sync'
    success_msg = f"Synchronized inventory for organization '{org.name}'"
    timestamp = datetime.now(UTC).strftime('%Y-%m-%d %H:%M')
    result = module_target_sat.execute(cmd)
    assert result.status == 0
    assert success_msg in result.stdout
    # Check task details
    wait_for(
        lambda: module_target_sat.api.ForemanTask()
        .search(query={'search': f'{inventory_sync_task} and started_at >= "{timestamp}"'})[0]
        .result
        == 'success',
        timeout=400,
        delay=15,
        silent_failure=True,
        handle_exception=True,
    )
    task_output = module_target_sat.api.ForemanTask().search(
        query={'search': f'{inventory_sync_task} and started_at >= "{timestamp}"'}
    )
    assert task_output[0].output['host_statuses']['sync'] == 2
    assert task_output[0].output['host_statuses']['disconnect'] == 0


def test_positive_sync_inventory_status_missing_host_ip(
    rhcloud_manifest_org,
    rhcloud_registered_hosts,
    module_target_sat,
):
    """Sync inventory status via foreman-rake commands with missing IP.

    :id: 372c03df-038b-49fb-a509-bb28edf178f3

    :steps:

        1. Create a vm and register to insights within org having manifest.
        2. Remove IP from host.
        3. Sync inventory status for specific organization.
            # export organization_id=1
            # /usr/sbin/foreman-rake rh_cloud_inventory:sync


    :expectedresults: Inventory status is successfully synced for satellite host with missing IP.

    :Verifies: SAT-24805

    :customerscenario: true
    """
    org = rhcloud_manifest_org
    cmd = f'organization_id={org.id} foreman-rake rh_cloud_inventory:sync'
    success_msg = f"Synchronized inventory for organization '{org.name}'"
    timestamp = datetime.now(UTC).strftime('%Y-%m-%d %H:%M')
    rhcloud_host = module_target_sat.cli.Host.info({'name': rhcloud_registered_hosts[0].hostname})[
        'id'
    ]
    update_ip = module_target_sat.execute(
        f'echo "Host.find({rhcloud_host}).update(ip: nil)" | foreman-rake console'
    )
    assert 'true' in update_ip.stdout
    result = module_target_sat.execute(cmd)
    assert result.status == 0
    assert success_msg in result.stdout
    # Check task details
    wait_for(
        lambda: module_target_sat.api.ForemanTask()
        .search(
            query={
                'search': f'{inventory_sync_task} and started_at >= "{timestamp}"',
                'per_page': 'all',
            }
        )[0]
        .result
        == 'success',
        timeout=400,
        delay=15,
        silent_failure=True,
        handle_exception=True,
    )
    task_output = module_target_sat.api.ForemanTask().search(
        query={'search': f'{inventory_sync_task} and started_at >= "{timestamp}"'}
    )
    host_status = None
    for task in task_output:
        if task.input.get("organization_ids") is None:
            continue
        if str(task.input.get("organization_ids")[0]) == str(org.id):
            host_status = task.output
            break
    assert host_status['host_statuses']['sync'] == 2
    assert host_status['host_statuses']['disconnect'] == 0


@pytest.mark.stubbed
def test_max_org_size_variable():
    """Verify that if organization had more hosts than specified by max_org_size variable
        then report won't be uploaded.

    :id: 7dd964c3-fde8-4335-ab13-02329119d7f6

    :steps:

        1. Register few content hosts with satellite.
        2. Change value of max_org_size for testing purpose(See BZ#1962694#c2).
        3. Start report generation and upload using
            ForemanTasks.sync_task(ForemanInventoryUpload::Async::GenerateAllReportsJob)

    :expectedresults: If organization had more hosts than specified by max_org_size variable
        then report won't be uploaded.

    :CaseImportance: Low

    :BZ: 1962694

    :CaseAutomation: ManualOnly
    """


@pytest.mark.stubbed
def test_satellite_inventory_slice_variable():
    """Test SATELLITE_INVENTORY_SLICE_SIZE dynflow environment variable.

    :id: ffbef1c7-08f3-444b-9255-2251d5594fcb

    :steps:

        1. Register few content hosts with satellite.
        2. Set SATELLITE_INVENTORY_SLICE_SIZE=1 dynflow environment variable.
            See BZ#1945661#c1
        3. Run "satellite-maintain service restart --only dynflow-sidekiq@worker-1"
        4. Generate inventory report.

    :expectedresults: Generated report had slice containing only one host.

    :CaseImportance: Low

    :BZ: 1945661

    :CaseAutomation: ManualOnly
    """


@pytest.mark.stubbed
def test_rhcloud_external_links():
    """Verify that all external links on Insights and Inventory page are working.

    :id: bc7f6354-ed3e-4ac5-939d-90bfe4177043

    :steps:

        1. Go to Configure > Inventory upload
        2. Go to Configure > Insights

    :expectedresults: all external links on Insights and Inventory page are working.

    :CaseImportance: Low

    :BZ: 1975093

    :CaseAutomation: ManualOnly
    """


def test_positive_generate_all_reports_job(target_sat):
    """Generate all reports job via foreman-rake console:

    :id: a9e4bfdb-6d7c-4f8c-ae57-a81442926dd8

    :steps:
        1. Disable the Automatic Inventory upload setting.
        2. Execute Foreman GenerateAllReportsJob via foreman-rake.

    :expectedresults: Reports generation works as expected.

    :BZ: 2110163

    :customerscenario: true

    :CaseAutomation: Automated
    """
    try:
        target_sat.update_setting('allow_auto_inventory_upload', False)
        with target_sat.session.shell() as sh:
            sh.send('foreman-rake console')
            time.sleep(30)  # sleep to allow time for console to open
            sh.send(f'ForemanTasks.async_task({generate_report_jobs})')
            time.sleep(3)  # sleep for the cmd execution
        timestamp = datetime.now(UTC).strftime('%Y-%m-%d %H:%M')
        wait_for(
            lambda: target_sat.api.ForemanTask()
            .search(query={'search': f'{generate_report_jobs} and started_at >= "{timestamp}"'})[0]
            .result
            == 'success',
            timeout=400,
            delay=15,
            silent_failure=True,
            handle_exception=True,
        )
        task_output = target_sat.api.ForemanTask().search(
            query={'search': f'{generate_report_jobs} and started_at >= {timestamp}'}
        )
        assert task_output[0].result == "success"
    finally:
        target_sat.update_setting('allow_auto_inventory_upload', True)


@pytest.mark.rhel_ver_match('N-2')
def test_positive_register_insights_client_host(module_target_sat, rhel_insights_vm):
    """Check the below command executed successfully
    command - insights-client --ansible-host=foo.example.com

    :id: b578371e-ec36-42de-83fa-bcea6e027fe2

    :setup:
        1. Enable, sync RHEL BaseOS and AppStream repositories
        2. Create CV, Publish/promote and create AK for host registration
        3. Register host to satellite, Setup Insights is Yes (Override), Install insights-client

    :steps:
        2. Test connection of insights client
        3. execute insight client command given in the description

    :expectedresults: Command executed successfully

    :Verifies: SAT-28695

    :customerscenario: true

    :CaseAutomation: Automated

    """
    # Test connection of insights client
    assert rhel_insights_vm.execute('insights-client --test-connection').status == 0

    # Execute insight client command
    output = rhel_insights_vm.execute(f'insights-client --ansible-host={rhel_insights_vm.hostname}')
    assert output.status == 0
    assert 'Ansible hostname updated' in output.stdout


def test_positive_check_report_autosync_setting(target_sat):
    """Verify that the Insights report autosync setting is enabled by default.

    :id: 137dffe6-50a4-4327-8e93-79e128bee63b

    :steps:
        1. Check the Insights report autosync setting.

    :expectedresults:
        1. The Insights setting "Synchronize recommendations Automatically" should have value "true"

    :Verifies: SAT-30227
    """
    assert (
        target_sat.cli.Settings.list({'search': 'Synchronize recommendations Automatically'})[0][
            'value'
        ]
        == 'true'
    ), 'Setting is not enabled by default!'
