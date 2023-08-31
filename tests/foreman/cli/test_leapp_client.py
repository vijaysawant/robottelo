"""Tests for leapp upgrade of content hosts with Satellite

:Requirement: leapp

:CaseLevel: Integration

:CaseComponent: LeappIntegration

:Team: Rocket

:TestType: Functional

:CaseImportance: High

:CaseAutomation: Automated

:Upstream: No
"""
import pytest
from broker import Broker

from robottelo.cli.activationkey import ActivationKey
from robottelo.cli.repository import Repository
from robottelo.config import settings
from robottelo.constants import PRDS
from robottelo.hosts import ContentHost
from robottelo.logging import logger

synced_repos = pytest.StashKey[dict]


@pytest.fixture(scope='module')
def module_stash(request):
    """Module scoped stash for storing data between tests"""
    # Please refer the documentation for more details on stash
    # https://docs.pytest.org/en/latest/reference/reference.html#stash
    request.node.stash[synced_repos] = {}
    yield request.node.stash


RHEL7_VER = '7.9'
RHEL8_VER = '8.8'
RHEL9_VER = '9.2'

RHEL_REPOS = {
    'rhel7_server': {
        'id': 'rhel-7-server-rpms',
        'name': f'Red Hat Enterprise Linux 7 Server RPMs x86_64 {RHEL7_VER}',
        'releasever': RHEL7_VER,
        'reposet': 'Red Hat Enterprise Linux 7 Server (RPMs)',
        'product': 'Red Hat Enterprise Linux Server',
    },
    'rhel7_server_extras': {
        'id': 'rhel-7-server-extras-rpms',
        'name': 'Red Hat Enterprise Linux 7 Server - Extras RPMs x86_64',
        'releasever': '7',
        'reposet': 'Red Hat Enterprise Linux 7 Server - Extras (RPMs)',
        'product': 'Red Hat Enterprise Linux Server',
    },
    'rhel8_bos': {
        'id': 'rhel-8-for-x86_64-baseos-rpms',
        'name': f'Red Hat Enterprise Linux 8 for x86_64 - BaseOS RPMs {RHEL8_VER}',
        'releasever': RHEL8_VER,
        'reposet': 'Red Hat Enterprise Linux 8 for x86_64 - BaseOS (RPMs)',
    },
    'rhel8_aps': {
        'id': 'rhel-8-for-x86_64-appstream-rpms',
        'name': f'Red Hat Enterprise Linux 8 for x86_64 - AppStream RPMs {RHEL8_VER}',
        'releasever': RHEL8_VER,
        'reposet': 'Red Hat Enterprise Linux 8 for x86_64 - AppStream (RPMs)',
    },
    'rhel9_bos': {
        'id': 'rhel-9-for-x86_64-baseos-rpms',
        'name': f'Red Hat Enterprise Linux 9 for x86_64 - BaseOS RPMs {RHEL9_VER}',
        'releasever': RHEL9_VER,
        'reposet': 'Red Hat Enterprise Linux 9 for x86_64 - BaseOS (RPMs)',
    },
    'rhel9_aps': {
        'id': 'rhel-9-for-x86_64-appstream-rpms',
        'name': f'Red Hat Enterprise Linux 9 for x86_64 - AppStream RPMs {RHEL9_VER}',
        'releasever': RHEL9_VER,
        'reposet': 'Red Hat Enterprise Linux 9 for x86_64 - AppStream (RPMs)',
    },
}


@pytest.fixture
def function_leapp_cv(module_target_sat, module_sca_manifest_org):
    logger.info('Creating Leapp Content View')
    return module_target_sat.api.ContentView(organization=module_sca_manifest_org).create()


@pytest.fixture(scope='module')
def module_leapp_lce(module_target_sat, module_sca_manifest_org):
    logger.info('Creating Leapp Lifecycle Environment')
    return module_target_sat.api.LifecycleEnvironment(organization=module_sca_manifest_org).create()


@pytest.fixture
def function_leapp_ak(
    module_target_sat, function_leapp_cv, module_leapp_lce, module_sca_manifest_org, upgrade_path
):
    logger.info(
        'Creating Leapp Activation Key for RHEL %s -> %s',
        upgrade_path['source_version'],
        upgrade_path['target_version'],
    )
    # need to publish and promote cv on lce to get content available on client host
    function_leapp_cv.publish()
    cvv = function_leapp_cv.read().version[0]
    cvv.promote(data={'environment_ids': module_leapp_lce.id, 'force': True})
    function_leapp_cv = function_leapp_cv.read()
    ak = module_target_sat.api.ActivationKey(
        content_view=function_leapp_cv,
        environment=module_leapp_lce,
        organization=module_sca_manifest_org,
    ).create()
    # In case of 'rhel7_server_extras' repos, need to enabled (overridden) repository
    # to get content available on client host
    if upgrade_path['source_version'].split('.')[0] == '7':
        ActivationKey.content_override(
            {
                'id': ak.id,
                'content-label': RHEL_REPOS['rhel7_server_extras']['id'],
                'value': 'true',
            }
        )
    return ak


@pytest.fixture
def verify_target_repo_on_satellite(
    module_target_sat,
    function_leapp_cv,
    module_sca_manifest_org,
    module_leapp_lce,
    upgrade_path,
    function_leapp_ak,
):
    """Verify target rhel version repositories has enabled on Satellite Server"""
    target_rhel_major_ver = upgrade_path['target_version'].split('.')[0]
    cmd_out = Repository.list(
        {
            'search': f'content_label ~ rhel-{target_rhel_major_ver}',
            'content-view-id': function_leapp_cv.id,
            'organization-id': module_sca_manifest_org.id,
            'lifecycle-environment-id': module_leapp_lce.id,
        }
    )
    repo_names = [out['name'] for out in cmd_out]
    if target_rhel_major_ver == '9':
        assert RHEL_REPOS['rhel9_bos']['name'] in repo_names
        assert RHEL_REPOS['rhel9_aps']['name'] in repo_names
    else:
        assert RHEL_REPOS['rhel8_bos']['name'] in repo_names
        assert RHEL_REPOS['rhel8_aps']['name'] in repo_names


@pytest.fixture
def register_host_with_satellite(
    module_target_sat,
    custom_leapp_host,
    module_sca_manifest_org,
):
    """Register content host with satellite"""
    logger.info(
        'Registering Leapp Host with Satellite - RHEL %s', custom_leapp_host.os_version.major
    )
    result = custom_leapp_host.register(
        module_sca_manifest_org, None, function_leapp_ak.name, module_target_sat
    )
    assert result.status == 0, f"Failed to register host: {result.stderr}"


@pytest.fixture
def precondition_check_upgrade_and_install_leapp_tool(custom_leapp_host):
    """Clean-up directory if in-place upgrade already performed,
    set rhel release version, update system and install leapp tool"""
    source_rhel_major_ver = custom_leapp_host.os_version.major
    logger.info(
        'Running precondition check for upgrade and install leapp tool - RHEL %s',
        source_rhel_major_ver,
    )
    source_rhel = str(custom_leapp_host.os_version)  # custom_leapp_host.deploy_rhel_version
    custom_leapp_host.run('rm -rf /root/tmp_leapp_py3')
    custom_leapp_host.run('yum clean all')
    custom_leapp_host.run('yum repolist')
    custom_leapp_host.run(f'subscription-manager release --set {source_rhel}')
    assert custom_leapp_host.run('yum update -y').status == 0
    assert custom_leapp_host.run('yum install leapp-upgrade -y').status == 0


@pytest.fixture
def fix_inhibitors(custom_leapp_host):
    """Fix inhibitors to avoid hard stop of Leapp tool execution"""
    source_rhel_major_ver = str(custom_leapp_host.os_version.major)
    logger.info('Fixing inhibitors for source rhel version %s', source_rhel_major_ver)
    # In case of Upgrade Path A - Rehl-8 to Rhel-9
    if source_rhel_major_ver == '8':
        # 1. Firewalld Configuration AllowZoneDrifting Is Unsupported
        custom_leapp_host.run(
            'sed -i "s/^AllowZoneDrifting=.*/AllowZoneDrifting=no/" /etc/firewalld/firewalld.conf'
        )
    else:
        # In case of Upgrade Path A - Rehl-7 to Rhel-8
        # Inhibitors could be fixed prior to run LEAPP-PREUPGRADE will place here
        pass
    # Newest installed kernel not in use
    if custom_leapp_host.run('needs-restarting -r').status == 1:
        custom_leapp_host.power_control(state='reboot', ensure=True)


@pytest.fixture
def leapp_sat_content(
    module_stash,
    custom_leapp_host,
    upgrade_path,
    module_target_sat,
    module_sca_manifest_org,
    function_leapp_cv,
    module_leapp_lce,
):
    """Enable rhel bos, aps repository and add it to the content view"""
    source = custom_leapp_host.os_version
    target = upgrade_path['target_version']
    all_repos = []
    logger.info('Enabling repositories for RHEL %s -> %s', source, target)
    for rh_repo_key in RHEL_REPOS.keys():
        release_version = RHEL_REPOS[rh_repo_key]['releasever']
        if release_version in str(source) or release_version in target:
            # prod = RHEL_REPOS[rh_repo_key]['product'] #rh_repo_key.split('_')[0]
            prod = 'rhel' if 'rhel7' in rh_repo_key else rh_repo_key.split('_')[0]
            if module_stash[synced_repos].get(rh_repo_key, None):
                logger.info("Repo %s already synced, not syncing it", rh_repo_key)
            else:
                logger.info('Enabling %s repository in product %s', rh_repo_key, prod)
                module_stash[synced_repos][rh_repo_key] = True
                repo_id = module_target_sat.api_factory.enable_rhrepo_and_fetchid(
                    basearch=custom_leapp_host.arch,
                    org_id=module_sca_manifest_org.id,
                    product=PRDS[prod],
                    repo=RHEL_REPOS[rh_repo_key]['name'],
                    reposet=RHEL_REPOS[rh_repo_key]['reposet'],
                    releasever=release_version,
                )
                rh_repo = module_target_sat.api.Repository(id=repo_id).read()
                all_repos.append(rh_repo)
                logger.info('Syncing %s repository', rh_repo_key)
                # sync repo
                rh_repo.sync(timeout=1800)
    function_leapp_cv.repository = all_repos
    function_leapp_cv = function_leapp_cv.update(['repository'])
    logger.info('Repos to be added to the AK: %s', all_repos)
    # Publish, promote content view to lce
    logger.info(f'Publish, promote cv - {function_leapp_cv.name} to lce - {module_leapp_lce.name}')
    function_leapp_cv.publish()
    cvv = function_leapp_cv.read().version[0]
    cvv.promote(data={'environment_ids': module_leapp_lce.id, 'force': True})
    function_leapp_cv = function_leapp_cv.read()


@pytest.fixture
def custom_leapp_host(upgrade_path):
    deploy_args = {}
    deploy_args['deploy_rhel_version'] = upgrade_path['source_version']
    logger.info('Creating Leapp Host - RHEL %s', deploy_args)
    with Broker(
        workflow='deploy-rhel',
        host_class=ContentHost,
        deploy_rhel_version=upgrade_path['source_version'],
        deploy_flavor=settings.flavors.default,
    ) as chost:
        yield chost


@pytest.mark.parametrize(
    'upgrade_path',
    [
        # {'source_version': RHEL7_VER, 'target_version': RHEL8_VER},
        {'source_version': RHEL8_VER, 'target_version': RHEL9_VER},
    ],
    ids=lambda upgrade_path: f'{upgrade_path["source_version"]}'
    f'_to_{upgrade_path["target_version"]}',
)
@pytest.mark.usefixtures(
    'leapp_sat_content',
    'register_host_with_satellite',
    'verify_target_repo_on_satellite',
    'precondition_check_upgrade_and_install_leapp_tool',
    'fix_inhibitors',
)
def test_leapp_upgrade_rhel(
    module_target_sat,
    custom_leapp_host,
    upgrade_path,
):
    """Test to upgrade RHEL host to next major RHEL Realse with Leapp Preupgrade and Leapp Upgrade
    Job templates

    :id: 8eccc689-3bea-4182-84f3-c121e95d54c3

    :Steps:
        1. Import a subscription manifest and enable, sync source & target repositories
        2. Create LCE, Create CV, add repositories to it, publish and promote CV, Create AK, etc.
        3. Register content host with AK
        4. Varify target rhel repositories are enable on Satellite
        5. Update all packages, install leapp tool and fix inhibitors
        6. Run Leapp Preupgrade and Leapp Upgrade job template

    :expectedresults:
        1. Update RHEL OS major version to another major version

    """
    logger.info('Running test for upgrade path %s', upgrade_path)
    old_ver = custom_leapp_host.os_version.major
    # 6. Run LEAPP-PREUPGRADE Job Template-
    template_id = (
        module_target_sat.api.JobTemplate()
        .search(query={'search': 'name="Run preupgrade via Leapp"'})[0]
        .id
    )
    job = module_target_sat.api.JobInvocation().run(
        synchronous=False,
        data={
            'job_template_id': template_id,
            'targeting_type': 'static_query',
            'search_query': f'name = {custom_leapp_host.hostname}',
        },
    )
    module_target_sat.wait_for_tasks(
        f'resource_type = JobInvocation and resource_id = {job["id"]}', poll_timeout=1800
    )
    result = module_target_sat.api.JobInvocation(id=job['id']).read()
    assert result.succeeded == 1
    # In case of Upgrade Path A - Rehl-7 to Rhel-8
    # Inhibitors should fix after running LEAPP-PREUPGRADE Job Template
    if upgrade_path['source_version'].split('.')[0] == '7':
        logger.info('Fixing inhibitory for upgrade path : %s', upgrade_path)
        # 1. Leapp detected loaded kernel drivers which have been removed in RHEL 8
        custom_leapp_host.run('rmmod floppy')
        custom_leapp_host.run('rmmod pata_acpi')
        # 2. Missing required answers in the answer file
        leapp_report_path = "/var/log/leapp/leapp-report.txt"
        grep_cmd = f"grep 'Title: Missing required answers in the answer file' {leapp_report_path}"
        if custom_leapp_host.run(grep_cmd).status == 0:
            custom_leapp_host.run(
                'leapp answer --section remove_pam_pkcs11_module_check.confirm=True'
            )

    # Run LEAPP-UPGRADE Job Template-
    template_id = (
        module_target_sat.api.JobTemplate()
        .search(query={'search': 'name="Run upgrade via Leapp"'})[0]
        .id
    )
    job = module_target_sat.api.JobInvocation().run(
        synchronous=False,
        data={
            'job_template_id': template_id,
            'targeting_type': 'static_query',
            'search_query': f'name = {custom_leapp_host.hostname}',
            'inputs': {'Reboot': 'true'},
        },
    )
    module_target_sat.wait_for_tasks(
        f'resource_type = JobInvocation and resource_id = {job["id"]}', poll_timeout=1800
    )
    result = module_target_sat.api.JobInvocation(id=job['id']).read()
    assert result.succeeded == 1
    # Wait for the host to be rebooted and SSH daemon to be started.
    custom_leapp_host.wait_for_connection()

    custom_leapp_host.clean_cached_properties()
    new_ver = custom_leapp_host.os_version.major
    assert new_ver == old_ver + 1
